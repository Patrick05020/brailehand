# SixSense <img width="49" height="55" alt="Screenshot 2026-10-06 at 2 55 11 PM" src="https://github.com/user-attachments/assets/f10822af-1e52-454b-afcb-0cace1ea9b87" />


**Speech you can feel.** SixSense is a wearable glove that turns spoken words into braille based vibration patterns, so deafblind people can follow a conversation by touch.

A USB microphone picks up speech, offline speech recognition turns it into text, and a Raspberry Pi pulses three vibrating rings on a glove in the pattern of each letter. Everything runs on the device, with no internet needed and no audio leaving it.

> Built at **Hack Dearborn 5**, where it won **3rd place**.



https://github.com/user-attachments/assets/e3931427-1830-4823-ae05-c111e474c40d


## How it works


1. **Listen:** `sounddevice` streams audio from the USB mic into [Vosk](https://alphacephei.com/vosk/), an offline speech recognizer.
2. **Encode:** each recognized letter is looked up in a table of standard 6-dot braille patterns.
3. **Vibrate:** the Pi switches its GPIO pins in time with the pattern, driving the vibration discs through transistors.

### Fitting 6-dot braille onto 3 rings

A braille cell has 6 dots, but the glove has 3 rings. So each letter is sent as **two pulses**: first the left column (dots 1-3), then the right column (dots 4-6).

| Letter | Pulse 1 (dots 1-3) | Pulse 2 (dots 4-6) |
|---|---|---|
| a | ● ○ ○ | ○ ○ ○ |
| h | ● ● ○ | ○ ● ○ |
| l | ● ● ● | ○ ○ ○ |

With three more discs, the same code could show a whole cell at once.


## Hardware

| Part | Notes |
|---|---|
| Raspberry Pi 4B+ | Runs everything |
| USB microphone | Any USB mic works |
| 3 × vibration discs | Adafruit Vibrating Mini Motor Discs |
| 3 × NPN transistors | e.g. 2N2222 / PN2222, one per disc |
| 3 × resistors | e.g. 1 kΩ, between each GPIO pin and its transistor base |
| 3 × diodes | e.g. 1N4001 / 1N4148, across each disc |
| Breadboard, jumper wires, glove | Electric Tape to hold the discs on the fingers |
| Soldering Iron | Optional but may be useful to solder the discs to jumper wire |

### Wiring (one ring)

GPIO pins can't power a vibration motor directly, so each disc has a small transistor driver:

- GPIO pin → resistor → transistor **base**
- Transistor **emitter** → Pi GND
- Disc between the supply rail (5 V from the Pi) and the transistor **collector**
- Diode across the disc, stripe toward the supply side
- All grounds connected together

| Ring | GPIO | Physical header pin |
|---|---|---|
| 1 | GPIO 26 | pin 37 |
| 2 | GPIO 19 | pin 35 |
| 3 | GPIO 13 | pin 33 |

The GPIO numbers are set in `main.py` (`DEFAULT_PINS`) and can be changed from the command line with `--pins`.

## Software

- Python 3
- [Vosk](https://alphacephei.com/vosk/) (offline speech-to-text)
- `sounddevice` (microphone input)
- `gpiozero` + `lgpio` (GPIO control on the Pi)
- Tkinter (start/stop window)

### Project files

| File | What it does |
|---|---|
| `main.py` | The pipeline: listening, braille encoding and motor output, with command line options |
| `gui.py` | A click to start/stop window that shows what was heard and lights up the three rings corresponding to each finger|
| `requirements.txt` | Python dependencies |

## Setup

### 1. Get the code

```bash
git clone https://github.com/Patrick05020/brailehand.git
cd brailehand
git checkout glove   # use main once the branches are merged
```

### 2. Create the environment and install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**On the Raspberry Pi:** `gpiozero` and `lgpio` already come with Raspberry Pi OS. If installing them fails, let the virtual environment use the system copies by setting `include-system-site-packages = true` in `.venv/pyvenv.cfg`, then reactivate the environment.

### 3. Download the speech model

Download `vosk-model-small-en-us-0.15` from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) and unzip it into a `models/` folder, so the path is `models/vosk-model-small-en-us-0.15`.

## Usage

The output type is chosen automatically: real vibrations on a Raspberry Pi, on-screen dots anywhere else.

```bash
# Click-to-start/stop window (run on the Pi's own screen)
python gui.py

# Listen to the microphone from the command line
python main.py --model models/vosk-model-small-en-us-0.15 --device "USB"

# Play typed text instead of speech (no mic or model needed)
python main.py --text "hello world"

# Buzz each ring once to check the wiring
python main.py --selftest
```

| Option | Meaning |
|---|---|
| `--model PATH` | Path to the unzipped Vosk model |
| `--device NAME` | Microphone name or index (list them with `python -m sounddevice`) |
| `--backend auto\|console\|gpio` | Force on-screen dots (`console`) or real vibrations (`gpio`) |
| `--pins 26,19,13` | GPIO numbers for rings 1, 2 and 3 |
| `--text "..."` | Play this text and exit |
| `--selftest` | Buzz each ring once and exit |

Timing (pulse length, gaps between letters and words) is set at the top of `main.py` and can be tuned by feel.

## Design decisions

- **Offline speech recognition (Vosk):** works without wifi, and speech never leaves the device.
- **Vibration discs, not buzzers:** piezo buzzers (provided by the MHL) are mostly sound and are hard to feel, so we used real vibration motors.
- **Two pulses per letter:** keeps the hardware to three motors.
- **Raspberry Pi GPIO directly:** decided against arduino (provided by MHL again) because the pi allowed for simpler wiring and more features
- **Swappable output backends:** the same code runs on a laptop for testing and on the Pi for real vibrations.

## Limitations and next steps

- Not yet tested with deaf-blind users or braille readers. Timing and practicality need feedback from them.
- Letters only: no numbers, or punctuational  braille yet.
- English speech model only.
- Next: more discs for a full 6-dot cell, a battery and enclosure, and a more wearable build as well as more user friendly interface.

## Team

- Ali Alfoaady, Software Lead
- Rayan Sidiqqui, Hardware Lead
- Patrick Mikha, Project Lead
- Hassan El-Sabeh, Marketing specialist

