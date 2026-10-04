"""Voice -> braille-like vibration prototype.

Runs on a Mac (console backend, no hardware) or a Raspberry Pi (GPIO backend).

  python main.py --model models/vosk-model-small-en-us-0.15            # live mic
  python main.py --text "hello world"                                  # no mic/model needed
  python main.py --model models/... --backend gpio                     # on the Pi
"""
import argparse
import json
import queue
import threading
import time

# Standard 6-dot braille: left column = dots 1,2,3 ; right column = dots 4,5,6
BRAILLE = {
    "a": {1}, "b": {1, 2}, "c": {1, 4}, "d": {1, 4, 5}, "e": {1, 5},
    "f": {1, 2, 4}, "g": {1, 2, 4, 5}, "h": {1, 2, 5}, "i": {2, 4}, "j": {2, 4, 5},
    "k": {1, 3}, "l": {1, 2, 3}, "m": {1, 3, 4}, "n": {1, 3, 4, 5}, "o": {1, 3, 5},
    "p": {1, 2, 3, 4}, "q": {1, 2, 3, 4, 5}, "r": {1, 2, 3, 5}, "s": {2, 3, 4},
    "t": {2, 3, 4, 5}, "u": {1, 3, 6}, "v": {1, 2, 3, 6}, "w": {2, 4, 5, 6},
    "x": {1, 3, 4, 6}, "y": {1, 3, 4, 5, 6}, "z": {1, 3, 5, 6},
}

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


# ---------- Output backends (same interface, swap with --backend) ----------
class ConsoleBackend:
    """Mac / no-hardware: prints rings as filled/empty circles."""
    def pulse(self, rings, duration):
        print("  " + " ".join("●" if r else "○" for r in rings), flush=True)
        time.sleep(duration)

    def close(self):
        pass


class GPIOBackend:
    """Raspberry Pi: drives ring motors straight from GPIO (no Arduino).
    Use a transistor/driver per motor (or Grove vibration-motor modules)."""
    def __init__(self, pins=(26, 19, 13)):
        from gpiozero import OutputDevice  # imported here so Mac doesn't need it
        self.rings = [OutputDevice(p) for p in pins]

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
            print(ch.upper())
            left, right = columns(ch)
            out.pulse(left, PULSE)
            time.sleep(COL_GAP)
            out.pulse(right, PULSE)
            time.sleep(LETTER_GAP)
        time.sleep(WORD_GAP)


def haptic_worker(text_q, out):
    """Plays queued text on its own thread so playback never blocks listening."""
    while True:
        text = text_q.get()
        if text is None:
            return
        play_text(text, out)


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
        print("Listening... Ctrl+C to stop")
        while True:
            if rec.AcceptWaveform(audio_q.get()):
                text = json.loads(rec.Result()).get("text", "")
                if text:
                    print(f"\nHeard: {text}")
                    text_q.put(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="path to an unzipped Vosk model folder")
    ap.add_argument("--text", help="skip the mic and play this text")
    ap.add_argument("--backend", choices=["console", "gpio"], default="console")
    ap.add_argument("--device", help="sounddevice input index or name (see: python -m sounddevice)")
    args = ap.parse_args()

    out = GPIOBackend() if args.backend == "gpio" else ConsoleBackend()
    if args.text:
        play_text(args.text, out)
        out.close()
        return
    if not args.model:
        ap.error("--model is required unless you use --text")

    text_q = queue.Queue()
    threading.Thread(target=haptic_worker, args=(text_q, out), daemon=True).start()
    try:
        listen(args.model, text_q, args.device)
    except KeyboardInterrupt:
        pass
    finally:
        text_q.put(None)
        out.close()


if __name__ == "__main__":
    main()
