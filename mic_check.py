"""
mic_check.py — raw microphone diagnostic, no bandpass filtering.
Shows raw ADC values, DC bias, and normalised RMS to diagnose
saturation, floating inputs, and wiring issues.

Usage:
    python3 mic_check.py              # 4 channels, SPI bus 0 device 0
    python3 mic_check.py --channels 0 1   # check only mics 0 and 1
    python3 mic_check.py --simulate       # test without hardware
"""

import argparse
import time
import numpy as np

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--channels",   nargs="+", type=int, default=[0, 1, 2, 3])
parser.add_argument("--spi-bus",    type=int, default=0)
parser.add_argument("--spi-device", type=int, default=0)
parser.add_argument("--frames",     type=int, default=256, help="samples per frame")
parser.add_argument("--simulate",   action="store_true")
args = parser.parse_args()

CHANNELS   = args.channels
FRAME_SIZE = args.frames
SIMULATE   = args.simulate
BAR_WIDTH  = 24

# ── SPI setup ─────────────────────────────────────────────────────────────────
spi = None
if not SIMULATE:
    try:
        import spidev
        spi = spidev.SpiDev()
        spi.open(args.spi_bus, args.spi_device)
        spi.max_speed_hz = 1_350_000
        print(f"✅ SPI opened — bus {args.spi_bus}, device {args.spi_device}\n")
    except Exception as e:
        print(f"❌ SPI failed: {e}")
        print("   Run with --simulate to test without hardware.\n")
        raise SystemExit(1)

# ── ADC read ──────────────────────────────────────────────────────────────────
def read_adc(ch: int) -> int:
    if spi is None:
        # Simulate a healthy mic: DC bias ~512, small audio swing
        return int(np.clip(512 + np.random.normal(0, 40), 0, 1023))
    cmd   = [1, (8 + ch) << 4, 0]
    reply = spi.xfer2(cmd)
    return ((reply[1] & 3) << 8) + reply[2]

# ── Interleaved frame capture — returns RAW 0-1023 ints ──────────────────────
def capture_frame() -> np.ndarray:
    raw = np.zeros((len(CHANNELS), FRAME_SIZE), dtype=float)
    for s in range(FRAME_SIZE):
        for i, ch in enumerate(CHANNELS):
            raw[i, s] = read_adc(ch)
    return raw   # NOT normalised yet — we want to see raw counts

# ── Diagnosis helper ──────────────────────────────────────────────────────────
def diagnose(mean: float, lo: int, hi: int, rms_norm: float) -> str:
    swing = hi - lo
    if swing < 5:
        if lo < 10:
            return "❌ RAIL LOW  — input shorted to GND or AGND wiring issue"
        if hi > 1018:
            return "❌ RAIL HIGH — input shorted to VCC or VREF issue"
        return "⚠️  FLAT      — input floating or mic not powered"
    if lo < 5 and hi > 1018:
        return "❌ CLIPPING  — input floating (random toggling between rails)"
    if mean < 200:
        return "⚠️  DC LOW    — mic bias voltage too low, check mic VCC / pull-up"
    if mean > 820:
        return "⚠️  DC HIGH   — mic output DC offset too high, check coupling cap"
    if rms_norm > 0.5 and swing > 800:
        return "⚠️  OVERLOAD  — mic too close to source or gain too high"
    if rms_norm < 0.005:
        return "⚠️  SILENT    — mic working but no sound detected"
    return "✅ OK"

def bar(value: float, width: int = BAR_WIDTH) -> str:
    filled = int(min(max(value, 0.0), 1.0) * width)
    return "█" * filled + "░" * (width - filled)

# ── Main loop ─────────────────────────────────────────────────────────────────
HEADER = (f"{'CH':<5} {'mean':>6}  {'lo–hi':^11}  {'DC bias':>7}  "
          f"{'norm RMS':>8}  {'level (×4)':<{BAR_WIDTH}}  diagnosis")
DIVIDER = "─" * len(HEADER)

print(f"Monitoring {len(CHANNELS)} mic(s), {FRAME_SIZE} samples/frame — Ctrl-C to stop")
print("MCP3008 raw counts (0–1023), DC midpoint should be ~512\n")

frame_count = 0
try:
    while True:
        t0  = time.perf_counter()
        raw = capture_frame()           # shape (n_ch, frame_size), raw counts
        elapsed_ms = (time.perf_counter() - t0) * 1000

        norm = (raw - 512.0) / 512.0   # normalise for RMS only

        frame_count += 1
        if frame_count > 1:
            print(f"\033[{len(CHANNELS) + 3}A", end="")

        print(f"  frame {frame_count:>5}   {elapsed_ms:.1f} ms/frame"
              f"   ({1000 * FRAME_SIZE / elapsed_ms / len(CHANNELS):.0f} Hz per ch)")
        print(DIVIDER)
        print(HEADER)
        print(DIVIDER)

        for i, ch in enumerate(CHANNELS):
            mean     = float(raw[i].mean())
            lo       = int(raw[i].min())
            hi       = int(raw[i].max())
            rms_norm = float(np.sqrt(np.mean(norm[i] ** 2)))
            dc_bias  = mean - 512.0     # how far from the ideal midpoint

            diag = diagnose(mean, lo, hi, rms_norm)
            level = bar(rms_norm * 4)

            print(f"ch{ch:<3} {mean:>6.0f}  [{lo:>4}–{hi:<4}]  "
                  f"{dc_bias:>+7.0f}  {rms_norm:>8.3f}  {level}  {diag}")

except KeyboardInterrupt:
    print("\n\n👋 Done.")
finally:
    if spi:
        spi.close()
