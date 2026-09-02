# magnus-g1 — working notes for Claude

A Unitree G1 humanoid that greets visitors in a showroom. A wireless-remote
button daemon runs **inside the robot**; this repo is what gets deployed there.
Your machine is a terminal, not a runtime — almost nothing here runs locally.

## The robot

| | |
| --- | --- |
| Jetson (PC2), where our code runs | `unitree@192.168.123.164` |
| Robot controller (PC1), audio + motion services | `192.168.123.161` |
| Laptop's own IP on that cable | `192.168.123.222` |
| Python on the robot | **3.8.10** (see traps) |
| Internet on the robot | **none, by design** |

Working copy on the robot: `/home/unitree/magnus/magnus-g1/`.
Service: `systemctl --user status magnus-buttons -l` (user unit, not a system one).

## What the buttons do

`routines/buttons.json` **on the robot** is the live config — it may differ from
the copy in git, because people edit it in place. Read it before changing it:

```bash
ssh unitree@192.168.123.164 'cat magnus/magnus-g1/routines/buttons.json'
```

Each button takes exactly one of `play` (a WAV), `tts` (built-in voice), or
`cmd` (a shell command). It hot-reloads in about a second; a malformed file is
rejected and the previous mapping keeps running.

## Traps that have actually bitten

**Python 3.8 on the robot, 3.11+ on laptops.** A `-> tuple[list[str], str]`
return annotation is evaluated at def time and crash-loops the service while
passing every test locally. Every module in `examples/` must start with
`from __future__ import annotations`; `tests/test_buttons.py` scans for it. This
shipped twice, because the guard first listed modules by name and a new file
wasn't on the list.

**Exit code 0 does not mean audible.** PulseAudio accepts a stream into an
output with nothing plugged in, so `paplay` returns 0 while the room hears
silence — six button presses once logged `finished` with no sound at all. Only a
person confirming counts as verification. Keep buttons on the SDK/DDS route
(the robot's own speaker); the Jetson's PulseAudio sinks only reach hardware
plugged into the Jetson.

**The daemon caches audio at startup.** After `scp`-ing a new WAV, restart it or
it keeps playing the old line while the file on disk looks correct:

```bash
ssh unitree@192.168.123.164 'systemctl --user restart magnus-buttons'
```

**Verify deploys by checksum, not file size.** Re-mastering audio preserves the
sample count, so the byte size often doesn't change at all.

**`journalctl --user` returns "No entries" on a healthy service** — this unit has
no persistent journal. Use `systemctl --user status magnus-buttons -l`.

**No passwordless sudo on the robot.** Never reach for `sudo systemctl`; the user
unit restarts without it.

## Audio rules

Firmware accepts **only 16 kHz mono 16-bit WAV**. Raw TTS lands near −25 LUFS,
which is inaudible in a room with people talking. Master every clip with the
chain in `scripts/boost_loudness.sh` (or the one in the Sparco SOP) to about
−12 dBFS mean. Six chains were measured; that one won. Past it you get
distortion, not volume.

Validate before deploying: `python examples/voice.py --check <file.wav>`.

## Arm routines

`routines/*.json`, run by `examples/arm_dance.py`. **Every routine must end with
`release arm`** — the G1 holds its last pose indefinitely, so a routine without
it leaves the robot frozen mid-gesture in front of guests.

Always dry-run before anyone presses the button:

```bash
python examples/arm_dance.py --dry-run --routine routines/<name>.json
```

Never trigger an arm routine remotely on a whim. Ask whoever is standing there
to confirm the arm has clear space first.

## House rules for changes

- Run `pytest tests/ -q` and `black` before committing. Tests are fast and
  require no robot.
- After changing code, import it under the **robot's** interpreter before
  restarting the service: `cd magnus/magnus-g1/examples && python3 -c "import button_trigger"`.
- Don't overwrite `routines/buttons.json` on the robot from the repo copy —
  patch it in place, or you will silently delete buttons someone else added.
- A deploy isn't done until a person heard or saw the result.

## Docs

- `docs/SOP-SPARCO-G1.md` — the operating and install SOP for the Sparco unit
- `docs/SETUP-WINDOWS.md` — get a fresh Windows machine talking to the robot
- `docs/SETUP.md` — full dev setup (only needed to run the SDK locally)
