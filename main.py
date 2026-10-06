"""Voice -> braille-like vibration prototype.

Runs on a Mac (console backend, no hardware) or a Raspberry Pi (GPIO backend).
The backend is picked automatically: GPIO on a Raspberry Pi, console elsewhere.

  python main.py --model models/vosk-model-small-en-us-0.15 --device "USB"   # live voice
  python main.py --text "hello world"                                         # typed text
  python main.py --selftest                                                   # buzz each ring once
  python main.py --backend console ...                                        # force on-screen dots
"""
import argparse
import json
import queue
import threading
import time
import traceback

# Standard 6-dot braille: left column = dots 1,2,3 ; right column = dots 4,5,6
BRAILLE = {
    "a": {1}, "b": {1, 2}, "c": {1, 4}, "d": {1, 4, 5}, "e": {1, 5},
    "f": {1, 2, 4}, "g": {1, 2, 4, 5}, "h": {1, 2, 5}, "i": {2, 4}, "j": {2, 4, 5},
    "k": {1, 3}, "l": {1, 2, 3}, "m": {1, 3, 4}, "n": {1, 3, 4, 5}, "o": {1, 3, 5},
    "p": {1, 2, 3, 4}, "q": {1, 2, 3, 4, 5}, "r": {1, 2, 3, 5}, "s": {2, 3, 4},
    "t": {2, 3, 4, 5}, "u": {1, 3, 6}, "v": {1, 2, 3, 6}, "w": {2, 4, 5, 6},
    "x": {1, 3, 4, 6}, "y": {1, 3, 4, 5, 6}, "z": {1, 3, 5, 6},
}

# GPIO numbers (not header pin numbers) for ring 1, 2, 3. Override with --pins 26,19,13
DEFAULT_PINS = (26, 19, 13)

# Timing (seconds) - tune these by feel once the glove is on a hand
PULSE = 0.30       # one braille column
COL_GAP = 0.10     # between the two columns of a letter
LETTER_GAP = 0.35  # between letters
WORD_GAP = 0.80    # between words


def columns(letter):
    """3 rings can't show 6 dots at once, so each letter = 2 pulses:
    first the left column (dots 1-3), then the right column (dots 4-6)."""
    dots = BRAILLE.get(letter, set())
    left = [(i + 1) in dots for i in range(3)]
    right = [(i + 4) in dots for i in range(3)]
    return left, right


def on_raspberry_pi():
    try:
        with open("/proc/device-tree/model") as f:
            return "Raspberry Pi" in f.read()
    except OSError:
        return False


# ---------- Output backends (same interface, swap with --backend) ----------
class ConsoleBackend:
    """Mac / no-hardware: prints rings as filled/empty circles."""
    name = "console (on-screen dots only, rings will NOT buzz)"

    def pulse(self, rings, duration):
        print("  " + " ".join("●" if r else "○" for r in rings), flush=True)
        time.sleep(duration)

    def close(self):
        pass


class GPIOBackend:
    """Raspberry Pi: drives ring motors straight from GPIO (no Arduino).
    Each pin goes through a transistor driver to its vibration disc."""

    def __init__(self, pins=DEFAULT_PINS):
        try:
            from gpiozero import OutputDevice  # imported here so Mac doesn't need it
        except ImportError:
            raise SystemExit("gpiozero is not available. On the Pi, make sure the venv "
                             "can see system packages (include-system-site-packages = true).")
        self.pins = tuple(pins)
        self.rings = [OutputDevice(p) for p in self.pins]
        self.name = f"gpio (rings on GPIO {', '.join(map(str, self.pins))})"

    def pulse(self, rings, duration):
        for dev, on in zip(self.rings, rings):
            dev.on() if on else dev.off()
        time.sleep(duration)
        for dev in self.rings:
            dev.off()

    def close(self):
        for dev in self.rings:
            dev.close()


def play_text(text, out):
    for word in text.lower().split():
        for ch in word:
            if ch not in BRAILLE:
                continue
            print(ch.upper(), flush=True)
            left, right = columns(ch)
            out.pulse(left, PULSE)
            time.sleep(COL_GAP)
            out.pulse(right, PULSE)
            time.sleep(LETTER_GAP)
        time.sleep(WORD_GAP)


def selftest(out):
    """Buzz each ring alone, then all three together."""
    for i in range(3):
        print(f"Ring {i + 1}")
        rings = [j == i for j in range(3)]
        out.pulse(rings, 0.6)
        time.sleep(0.3)
    print("All rings")
    out.pulse([True, True, True], 0.6)


def haptic_worker(text_q, out):
    """Plays queued text on its own thread so playback never blocks listening.
    Errors are printed instead of silently killing the thread."""
    while True:
        text = text_q.get()
        if text is None:
            return
        try:
            play_text(text, out)
        except Exception:
            traceback.print_exc()


def listen(model_path, text_q, device=None):
    import sounddevice as sd
    from vosk import KaldiRecognizer, Model

    rate = int(sd.query_devices(device, "input")["default_samplerate"])
    rec = KaldiRecognizer(Model(model_path), rate)
    audio_q = queue.Queue()

    def callback(indata, frames, t, status):
        audio_q.put(bytes(indata))

    with sd.RawInputStream(samplerate=rate, blocksize=8000, dtype="int16",
                           channels=1, device=device, callback=callback):
        print("Listening... Ctrl+C to stop", flush=True)
        while True:
            if rec.AcceptWaveform(audio_q.get()):
                text = json.loads(rec.Result()).get("text", "")
                if text:
                    print(f"\nHeard: {text}", flush=True)
                    text_q.put(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="path to an unzipped Vosk model folder")
    ap.add_argument("--text", help="skip the mic and play this text")
    ap.add_argument("--backend", choices=["auto", "console", "gpio"], default="auto",
                    help="auto = gpio on a Raspberry Pi, console elsewhere")
    ap.add_argument("--pins", help="GPIO numbers for rings 1,2,3 (default 26,19,13)")
    ap.add_argument("--device", help="sounddevice input index or name (see: python -m sounddevice)")
    ap.add_argument("--selftest", action="store_true", help="buzz each ring once and exit")
    args = ap.parse_args()

    backend = args.backend
    if backend == "auto":
        backend = "gpio" if on_raspberry_pi() else "console"
    pins = tuple(int(p) for p in args.pins.split(",")) if args.pins else DEFAULT_PINS

    out = GPIOBackend(pins) if backend == "gpio" else ConsoleBackend()
    print(f"Output: {out.name}", flush=True)

    if args.selftest:
        selftest(out)
        out.close()
        return
    if args.text:
        play_text(args.text, out)
        out.close()
        return
    if not args.model:
        ap.error("--model is required unless you use --text or --selftest")

    text_q = queue.Queue()
    worker = threading.Thread(target=haptic_worker, args=(text_q, out), daemon=True)
    worker.start()
    try:
        listen(args.model, text_q, args.device)
    except KeyboardInterrupt:
        pass
    finally:
        text_q.put(None)
        worker.join(timeout=5)
        out.close()


if __name__ == "__main__":
    main()

