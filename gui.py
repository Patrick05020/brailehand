"""Click-to-start/stop window for the braille glove (run on the Pi's own screen).

  python gui.py
  python gui.py --device "USB" --model models/vosk-model-small-en-us-0.15
"""
import argparse
import queue
import threading
import tkinter as tk

import main as core

GREEN, RED, GREY, YELLOW = "#2e9e4f", "#c0392b", "#555555", "#f1c40f"


class GuiBackend:
    """Wraps the real backend (GPIO or console) and mirrors each pulse on screen."""

    def __init__(self, real, ui_q):
        self.real, self.ui_q = real, ui_q
        self.name = real.name

    def pulse(self, rings, duration):
        self.ui_q.put(("rings", list(rings)))
        try:
            self.real.pulse(rings, duration)
        finally:
            self.ui_q.put(("rings", [False, False, False]))

    def close(self):
        self.real.close()


class App:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.ui_q = queue.Queue()
        self.text_q = queue.Queue()
        self.stop_event = threading.Event()
        self.cancel = threading.Event()
        self.listener = None

        backend = args.backend
        if backend == "auto":
            backend = "gpio" if core.on_raspberry_pi() else "console"
        pins = tuple(int(p) for p in args.pins.split(",")) if args.pins else core.DEFAULT_PINS
        real = core.GPIOBackend(pins) if backend == "gpio" else core.ConsoleBackend()
        self.out = GuiBackend(real, self.ui_q)

        # Haptic playback thread lives for the whole session
        threading.Thread(target=core.haptic_worker,
                         args=(self.text_q, self.out, self.cancel), daemon=True).start()

        root.title("Braille Glove")
        root.geometry("460x420")
        root.configure(bg="#1e1e1e")

        self.button = tk.Button(root, text="START", font=("Helvetica", 32, "bold"),
                                bg=GREEN, fg="white", activebackground=GREEN,
                                width=10, height=2, command=self.toggle)
        self.button.pack(pady=(25, 10))

        self.status = tk.Label(root, text="Stopped", font=("Helvetica", 16),
                               bg="#1e1e1e", fg="white")
        self.status.pack()

        tk.Label(root, text=f"Output: {self.out.name}", font=("Helvetica", 9),
                 bg="#1e1e1e", fg="#aaaaaa", wraplength=420).pack(pady=(2, 10))

        self.canvas = tk.Canvas(root, width=300, height=90, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()
        self.lights = [self.canvas.create_oval(20 + i * 100, 15, 80 + i * 100, 75,
                                               fill=GREY, outline="white", width=2)
                       for i in range(3)]

        tk.Label(root, text="Last heard:", font=("Helvetica", 11),
                 bg="#1e1e1e", fg="#aaaaaa").pack(pady=(15, 0))
        self.heard = tk.Label(root, text="-", font=("Helvetica", 18),
                              bg="#1e1e1e", fg="white", wraplength=420)
        self.heard.pack()

        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.poll()

    # ---- button logic ----
    def toggle(self):
        if self.listener is None:
            self.start()
        else:
            self.stop()

    def start(self):
        self.stop_event.clear()
        self.cancel.clear()
        self.button.config(text="LOADING...", state="disabled", bg=GREY)
        self.status.config(text="Loading speech model...")
        self.listener = threading.Thread(target=self.run_listener, daemon=True)
        self.listener.start()

    def run_listener(self):
        try:
            core.listen(self.args.model, self.text_q, self.args.device,
                        stop_event=self.stop_event,
                        on_text=lambda t: self.ui_q.put(("heard", t)),
                        on_ready=lambda: self.ui_q.put(("ready", None)))
        except Exception as e:  # show mic/model problems on screen
            self.ui_q.put(("error", str(e)))
        self.ui_q.put(("stopped", None))

    def stop(self):
        self.button.config(text="STOPPING...", state="disabled", bg=GREY)
        self.stop_event.set()
        self.cancel.set()  # cut off any vibration in progress
        while True:        # drop anything still waiting to be vibrated
            try:
                self.text_q.get_nowait()
            except queue.Empty:
                break

    # ---- screen updates (always on the Tk thread) ----
    def poll(self):
        try:
            while True:
                kind, value = self.ui_q.get_nowait()
                if kind == "ready":
                    self.button.config(text="STOP", state="normal", bg=RED, activebackground=RED)
                    self.status.config(text="Listening...")
                elif kind == "heard":
                    self.heard.config(text=value)
                elif kind == "rings":
                    for light, on in zip(self.lights, value):
                        self.canvas.itemconfig(light, fill=YELLOW if on else GREY)
                elif kind == "error":
                    self.status.config(text=f"Error: {value}")
                elif kind == "stopped":
                    self.listener = None
                    self.button.config(text="START", state="normal", bg=GREEN, activebackground=GREEN)
                    if not self.status.cget("text").startswith("Error"):
                        self.status.config(text="Stopped")
        except queue.Empty:
            pass
        self.root.after(50, self.poll)

    def quit(self):
        self.stop_event.set()
        self.cancel.set()
        self.out.close()
        self.root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/vosk-model-small-en-us-0.15")
    ap.add_argument("--device", default="USB", help='mic name or index (default "USB")')
    ap.add_argument("--backend", choices=["auto", "console", "gpio"], default="auto")
    ap.add_argument("--pins", help="GPIO numbers for rings 1,2,3 (default 26,19,13)")
    args = ap.parse_args()
    root = tk.Tk()
    App(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
