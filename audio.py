import numpy as np
import time
from scipy.signal import cheby2, sosfilt, sosfilt_zi
from config import Config

class AudioCapture:
    def __init__(self, config: Config):
        self.config      = config
        self.simulate    = config.simulate
        self.sample_rate = config.sample_rate_hz
        self.frame_size  = config.frame_size
        self.channels    = config.channels
        self.freq_bands  = config.mic_freq_bands

        self._filters = []
        self._zi      = []

        if not self.simulate:
            try:
                import spidev
                self.spi = spidev.SpiDev()
                self.spi.open(config.spi_bus, config.spi_device)
                self.spi.max_speed_hz = 1350000
                print("✅ Hardware SPI initialised on Raspberry Pi 5")
                self._calibrate_sample_rate()   # measure real rate BEFORE building filters
            except Exception as e:
                print(f"❌ Failed to initialise SPI: {e}")
                print("   Falling back to simulation mode")
                self.simulate = True

        self._build_filters()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _calibrate_sample_rate(self):
        """Time 128 real ADC reads and update self.sample_rate to match."""
        N = 128
        t0 = time.perf_counter()
        for _ in range(N):
            self.read_mcp3008(0)
        actual = N / (time.perf_counter() - t0)

        ratio = actual / self.sample_rate
        print(f"  📏 Measured ADC rate : {actual:.0f} Hz")
        print(f"     Configured rate   : {self.sample_rate} Hz  (ratio {ratio:.3f})")

        if abs(ratio - 1.0) > 0.05:
            print(f"  ⚠️  Rate mismatch > 5% — rebuilding filters for {actual:.0f} Hz")
            self.sample_rate = actual          # filters will use this corrected rate
            self.config.sample_rate_hz = actual  # localization.py reads from config directly

    def _build_filters(self):
        """Build per-channel Chebyshev Type 2 bandpass filters for the current sample rate."""
        nyquist = self.sample_rate / 2.0
        self._filters = []
        self._zi      = []

        # Per-channel gain correction — normalises each mic to the same
        # baseline sensitivity. Values are (min_rms / channel_rms) so the
        # quietest mic = 1.0 and louder mics are scaled down to match.
        # Update mic_rms_calibration in config.json from mic_check.py output.
        raw_rms = np.array(self.config.mic_rms_calibration)
        self._channel_gains = raw_rms.min() / raw_rms
        print(f"  🎛️  Per-channel gain corrections: "
              + ", ".join(f"ch{self.channels[i]}={g:.3f}"
                          for i, g in enumerate(self._channel_gains)))

        for i, (low, high) in enumerate(self.freq_bands):
            # Safety clamp: keep edges strictly inside (0, Nyquist)
            low_n  = max(low,  1.0)          / nyquist
            high_n = min(high, nyquist * 0.99) / nyquist

            if low_n >= high_n:
                print(f"  ❌ Mic {i+1}: band [{low}-{high} Hz] is invalid at "
                      f"Nyquist {nyquist:.0f} Hz — check sample_rate_hz in config")
                # Fall back to a safe wide band so we don't crash
                low_n, high_n = 0.5, 0.9

            sos = cheby2(4, 60, [low_n, high_n], btype='band', output='sos')
            self._filters.append(sos)
            self._zi.append(sosfilt_zi(sos))

            actual_low  = low_n  * nyquist
            actual_high = high_n * nyquist
            print(f"  🎚️  Mic {i+1} (ch {self.channels[i]}): "
                  f"filter {actual_low:.0f}–{actual_high:.0f} Hz  "
                  f"(target {low}–{high} Hz)")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bandpass(self, signal: np.ndarray, channel_idx: int) -> np.ndarray:
        """Bandpass-filter signal, preserving state across frames."""
        # Scale zi by the first sample to prevent DC-step transient at frame boundaries
        zi = self._zi[channel_idx] * signal[0]
        out, self._zi[channel_idx] = sosfilt(
            self._filters[channel_idx], signal, zi=zi
        )
        return out

    def _apply_sensitivity(self, signal: np.ndarray, channel_idx: int) -> np.ndarray:
        """Apply per-channel gain correction, noise gate, then global gain."""
        signal = signal * self._channel_gains[channel_idx]   # level-match channels
        rms = np.sqrt(np.mean(signal ** 2))
        if rms < self.config.noise_gate_threshold:
            return np.zeros_like(signal)
        return signal * self.config.mic_gain

    def read_mcp3008(self, channel: int) -> int:
        """Read one 10-bit sample from MCP3008 via SPI."""
        if self.simulate:
            return np.random.randint(0, 1024)
        cmd   = [1, (8 + channel) << 4, 0]
        reply = self.spi.xfer2(cmd)
        return ((reply[1] & 3) << 8) + reply[2]

    # ------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def get_frame(self) -> np.ndarray:
        """Return one filtered frame  (shape: n_channels × n_samples).

        Simulation: each mic generates a sine at the centre of its assigned
        band so the UI shows clearly different activity per channel.

        Hardware: raw 10-bit ADC values are normalised to [-1, 1] then
        bandpass-filtered through the channel's persistent filter state.
        """
        data = np.zeros((len(self.channels), self.frame_size))

        if self.simulate:
            t = np.arange(self.frame_size) / self.sample_rate
            for i, (low, high) in enumerate(self.freq_bands):
                center = (low + high) / 2.0
                raw = (np.sin(2 * np.pi * center * t) * 0.4
                       + np.random.normal(0, 0.15, self.frame_size))
                data[i] = self._apply_sensitivity(self._bandpass(raw, i), i)
            return data

        # Hardware: read ADC → normalise → filter
        for i, ch in enumerate(self.channels):
            raw = np.array(
                [self.read_mcp3008(ch) for _ in range(self.frame_size)],
                dtype=float
            )
            raw    = (raw - 512.0) / 512.0     # 10-bit ADC → [-1, 1]
            data[i] = self._apply_sensitivity(self._bandpass(raw, i), i)
        return data
