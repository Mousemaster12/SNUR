import json
import argparse
from pathlib import Path

class Config:
    def __init__(self):
        self.simulate = False 
        self.sample_rate_hz = 8000
        self.frame_size = 256
        self.speed_of_sound_mps = 343.0
        # 4 mics at tetrahedral corners of a 0.2 m cube — best spread for 3D TDOA.
        # Each pair of mics differs in exactly 2 axes so the geometry is fully 3D.
        #   corner 0: origin          corner 1: XY diagonal
        #   corner 2: XZ diagonal     corner 3: YZ diagonal
        self.mic_positions = [
            [0.0, 0.0, 0.0],
            [0.2, 0.2, 0.0],
            [0.2, 0.0, 0.2],
            [0.0, 0.2, 0.2],
        ]
        self.search_bounds = [-2.0, 2.0, -2.0, 2.0, 0.0, 4.0]  # xmin,xmax,ymin,ymax,zmin,zmax
        self.search_step_m = 0.1   # coarser step keeps 3D grid to ~41^3 = 69k pts
        self.channels = [0, 1, 2, 3]
        self.spi_bus = 0
        self.spi_device = 0
        self.ui_bind_host = "0.0.0.0"
        self.ui_bind_port = 8080
        self.calibration_offsets_s = [0.0, 0.0, 0.0, 0.0]
        # 200 Hz wide, 200 Hz apart, high-frequency only (3000 Hz+).
        # Nyquist limit for 8 kHz sample rate is 4000 Hz — all bands clear it.
        self.mic_freq_bands = [[3000, 3200], [3200, 3400], [3400, 3600], [3600, 3800]]
        # Sensitivity controls (tune these to match your environment):
        #   noise_gate_threshold — per-channel RMS below this is zeroed out entirely.
        #                          0.0 = gate off.  Range roughly 0.0–0.5 on normalised signal.
        #   mic_gain             — multiplier applied after filtering and gating.
        #                          < 1.0 = less sensitive, > 1.0 = more sensitive.
        self.noise_gate_threshold = 0.02
        self.mic_gain             = 1.0
        # Per-channel RMS measured from mic_check.py in silence.
        # Used to normalise all mics to the same baseline sensitivity.
        # Re-run mic_check.py and update these if you change hardware.
        self.mic_rms_calibration  = [0.174, 0.193, 0.186, 0.196]
        self.debug = True

    def load(self, config_path: str = None):
        # If no path given, look for config.json next to this file automatically
        if not config_path:
            config_path = Path(__file__).parent / "config.json"
        
        path = Path(config_path)
        if not path.exists():
            print(f"⚠️ Config file not found: {config_path}. Using defaults.")
            return self

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ config.json has a syntax error and could not be loaded: {e}")
            print("   Using defaults — fix config.json to apply your settings.")
            return self

        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                print(f"⚠️  Unknown config key ignored: '{key}'")

        print(f"✅ Loaded config from {path}")
        return self


def parse_args():
    parser = argparse.ArgumentParser(description="Snur - Sound Localization")
    parser.add_argument('--config', type=str, help='Path to config.json file')
    return parser.parse_args()
