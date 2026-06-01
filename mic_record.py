"""
mic_record.py — record audio from MCP3008 microphones and save as WAV.
Strips DC bias in software (fixes the DC-high issue without hardware changes).

Usage:
    python3 mic_record.py                  # record all 4 channels, 5 seconds
    python3 mic_record.py --channels 0 1   # only channels 0 and 1
    python3 mic_record.py --seconds 10     # record for 10 seconds
    python3 mic_record.py --out /tmp       # save WAVs to /tmp/
    python3 mic_record.py --simulate       # test without hardware
"""

import argparse
import time
import wave
import struct
import numpy as np

# ── CLI args ──────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--channels",   nargs="+", type=int, default=[0, 1, 2, 3])
parser.add_argument("--spi-bus",    type=int, default=0)
parser.add_argument("--spi-device", type=int, default=0)
parser.add_argument("--rate",       type=int, default=8000, help="sample rate Hz")
parser.add_argument("--seconds",    type=float, default=5.0)
parser.add_argument("--out",        type=str,   default=".")
parser.add_argument("--simulate",   action="store_true")
args = parser.parse_args()

CHANNELS   = args.channels
RATE       = args.rate
SECONDS    = args.seconds
OUT_DIR    = args.out
N_SAMPLES  = int(RATE * SECONDS)

# ── SPI setup ─────────────────────────────────────────────────────────────────
spi = None
if not args.simulate:
    try:
        import spidev
        spi = spidev.SpiDev()
        spi.open(args.spi_bus, args.spi_device)
        spi.max_speed_hz = 1_350_000
        print(f"✅ SPI opened — bus {args.spi_bus}, device {args.spi_device}")
    except Exception as e:
        print(f"❌ SPI failed: {e}\n   Run with --simulate to test without hardware.")
        raise SystemExit(1)

# ── ADC read ──────────────────────────────────────────────────────────────────
def read_adc(ch: int) -> int:
    if spi is None:
        # Simulate: 300 Hz tone + noise, with a DC offset to mimic the DC-high issue
        t = time.perf_counter()
        return int(np.clip(800 + 80 * np.sin(2 * np.pi * 300 * t)
                           + np.random.normal(0, 10), 0, 1023))
    cmd   = [1, (8 + ch) << 4, 0]
    reply = spi.xfer2(cmd)
    return ((reply[1] & 3) << 8) + reply[2]

# ── Record ────────────────────────────────────────────────────────────────────
print(f"\nRecording {SECONDS}s from channels {CHANNELS} at {RATE} Hz ...")
print("Speak or make noise near the mics now.\n")

# Buffer: shape (n_channels, n_samples) — raw 0–1023 counts
buf = np.zeros((len(CHANNELS), N_SAMPLES), dtype=np.float32)

t_start = time.perf_counter()
for s in range(N_SAMPLES):
    for i, ch in enumerate(CHANNELS):
        buf[i, s] = read_adc(ch)

    # Progress bar every 0.5 s worth of samples
    if s % (RATE // 2) == 0:
        elapsed   = time.perf_counter() - t_start
        remaining = SECONDS - elapsed
        pct       = s / N_SAMPLES
        filled    = int(pct * 30)
        bar       = "█" * filled + "░" * (30 - filled)
        print(f"  [{bar}] {elapsed:.1f}s / {SECONDS:.1f}s  ({remaining:.1f}s left)",
              end="\r", flush=True)

elapsed = time.perf_counter() - t_start
print(f"\n\n✅ Captured {N_SAMPLES} samples in {elapsed:.2f}s "
      f"(actual rate: {N_SAMPLES/elapsed:.0f} Hz per channel)")

# ── DC removal + normalise ────────────────────────────────────────────────────
# Subtract per-channel mean to strip DC bias — this is what the coupling cap
# should do in hardware. Audio content is unaffected.
print("\nChannel stats (raw ADC counts):")
print(f"  {'ch':<5} {'mean':>7}  {'DC offset':>10}  {'swing':>7}  {'after DC removal RMS':>20}")
print("  " + "─" * 60)

processed = np.zeros_like(buf)
for i, ch in enumerate(CHANNELS):
    raw_mean  = buf[i].mean()
    dc_offset = raw_mean - 512.0
    ac        = buf[i] - raw_mean          # remove DC
    peak      = np.abs(ac).max()
    norm      = ac / (peak + 1e-9)         # normalise to [-1, 1]
    processed[i] = norm
    rms_after = float(np.sqrt(np.mean(norm ** 2)))
    print(f"  ch{ch:<3} {raw_mean:>7.0f}  {dc_offset:>+10.0f}  "
          f"{int(buf[i].max()-buf[i].min()):>7}  {rms_after:>20.4f}")

# ── Save WAV files ─────────────────────────────────────────────────────────────
# One WAV per channel so you can listen to each independently.
# Also save a combined multi-channel WAV.
timestamp = time.strftime("%Y%m%d_%H%M%S")
saved = []

for i, ch in enumerate(CHANNELS):
    filename = f"{OUT_DIR}/mic_ch{ch}_{timestamp}.wav"
    pcm = (processed[i] * 32767).astype(np.int16)
    with wave.open(filename, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(RATE)
        wf.writeframes(pcm.tobytes())
    saved.append(filename)
    print(f"  💾 ch{ch} → {filename}")

# Combined (interleaved multi-channel WAV)
combined_file = f"{OUT_DIR}/mic_all_{timestamp}.wav"
interleaved = np.stack([
    (processed[i] * 32767).astype(np.int16) for i in range(len(CHANNELS))
], axis=1).flatten()
with wave.open(combined_file, "w") as wf:
    wf.setnchannels(len(CHANNELS))
    wf.setsampwidth(2)
    wf.setframerate(RATE)
    wf.writeframes(interleaved.tobytes())
saved.append(combined_file)

print(f"\n  🎵 combined ({len(CHANNELS)}ch) → {combined_file}")
print(f"\nDone. Open the WAV files with Audacity or:")
print(f"  aplay -r {RATE} -f S16_LE -c 1 {OUT_DIR}/mic_ch{CHANNELS[0]}_{timestamp}.wav")

if spi:
    spi.close()
