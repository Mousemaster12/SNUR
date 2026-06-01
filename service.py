import threading
import time
import json
from pathlib import Path
from config import Config
from audio import AudioCapture
from localization import SoundLocalizer

class LocalizationService:
    def __init__(self, config: Config):
        self.config = config
        self.audio = AudioCapture(config)
        self.localizer = SoundLocalizer(config)
        self.latest_result = {
            "position": [0.0, 0.0],
            "error": 0.0,
            "tdoas": [0.0, 0.0, 0.0, 0.0],
            "powers": [0.0, 0.0, 0.0, 0.0]
        }
        self.running = False
        self.thread = None
        self.snapshot_dir = Path("../snapshots")
        self.snapshot_dir.mkdir(exist_ok=True)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.thread.start()
        print("🚀 Localization service started (Raspberry Pi 5)")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _processing_loop(self):
        while self.running:
            try:
                frame = self.audio.get_frame()
                result = self.localizer.process_frame(frame)
                
                self.latest_result = result
                
                # Save snapshot every few seconds
                if int(time.time()) % 3 == 0:
                    self._save_snapshot(result)
                    
            except Exception as e:
                print(f"Error in processing: {e}")
                time.sleep(0.2)

    def _save_snapshot(self, result):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        data = {"timestamp": timestamp, **result}
        try:
            with open(self.snapshot_dir / f"snapshot_{timestamp}.json", "w") as f:
                json.dump(data, f, indent=2)
        except:
            pass  # Ignore snapshot errors

    def get_latest(self):
        return self.latest_result
