import numpy as np
from scipy.signal import correlate

class SoundLocalizer:
    def __init__(self, config):
        self.config = config
        self.mic_positions = np.array(config.mic_positions, dtype=float)  # (n_mics, 3)
        self.speed_of_sound = config.speed_of_sound_mps
        self.calibration_offsets = np.array(config.calibration_offsets_s)

    def compute_tdoa(self, signals: np.ndarray):
        """Compute Time Difference of Arrival relative to first microphone."""
        n_mics = signals.shape[0]
        tdoas = np.zeros(n_mics - 1)
        ref = signals[0]

        for i in range(1, n_mics):
            corr = correlate(signals[i], ref, mode='full')
            lag = np.argmax(corr) - (len(ref) - 1)
            tdoas[i - 1] = lag / self.config.sample_rate_hz

        return tdoas - self.calibration_offsets[1:]

    def grid_search(self, tdoas: np.ndarray):
        """Vectorised 3-D grid search for device position.

        Uses numpy broadcasting so the entire error surface is computed in a
        handful of array operations instead of a triple Python loop.
        """
        xmin, xmax, ymin, ymax, zmin, zmax = self.config.search_bounds
        step = self.config.search_step_m

        x = np.arange(xmin, xmax + step / 2, step)
        y = np.arange(ymin, ymax + step / 2, step)
        z = np.arange(zmin, zmax + step / 2, step)

        # Shape broadcast: (nx,1,1), (1,ny,1), (1,1,nz) → (nx,ny,nz)
        X = x[:, None, None]
        Y = y[None, :, None]
        Z = z[None, None, :]

        error = np.zeros((len(x), len(y), len(z)), dtype=np.float32)

        ref = self.mic_positions[0]  # (3,)
        dist_ref = np.sqrt((X - ref[0]) ** 2 + (Y - ref[1]) ** 2 + (Z - ref[2]) ** 2)

        for k in range(1, len(self.mic_positions)):
            mic = self.mic_positions[k]
            dist_mic = np.sqrt((X - mic[0]) ** 2 + (Y - mic[1]) ** 2 + (Z - mic[2]) ** 2)
            predicted_tdoa = (dist_mic - dist_ref) / self.speed_of_sound
            diff = predicted_tdoa - tdoas[k - 1]
            error += (diff * diff).astype(np.float32)

        idx = int(np.argmin(error))
        ix, iy, iz = np.unravel_index(idx, error.shape)

        position = [float(x[ix]), float(y[iy]), float(z[iz])]
        return position, float(error.flat[idx])

    def process_frame(self, signals: np.ndarray):
        """Main processing: TDOA → 3-D device position."""
        tdoas    = self.compute_tdoa(signals)
        position, error = self.grid_search(tdoas)
        powers   = np.mean(signals ** 2, axis=1).tolist()

        return {
            "position": position,          # [x, y, z] in metres
            "error":    float(error),
            "tdoas":    [0.0] + tdoas.tolist(),
            "powers":   powers,
        }
