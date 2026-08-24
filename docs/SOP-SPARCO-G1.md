# SOP — Sparco G1 (showroom greeter)

The second G1. Everything below was run on the unit at Sparco on 2026-08-25, not
copied from the first robot's docs — that unit had three things this one does
not, and the standard installer fails here because of it (see §5).

**Unit:** Jetson (PC2) `192.168.123.164`, robot controller (PC1)
`192.168.123.161`, Python 3.8.10, aarch64.

---

## 1. What it does

| Button | Behaviour | Path |
| --- | --- | --- |
| **RB** | Says *"Hello. Welcome to Sparco! Your IT solution provider!"* (3.8 s) | SDK → robot's own speaker |
| **R2** | Says the same line **while waving**, then lowers the arm (7.5 s) | Same, plus the arm action client |
| **LB** | Built-in TTS: *"Hello! Thanks for visiting…"* | Robot TTS |

**All three work with no network of any kind.** They talk to the robot's own
computer over the DDS bus inside the body. The neck Ethernet cable is only for
a laptop to log in — unplug it and the buttons keep working.

Volume is pinned to 100 (the SDK maximum) and asserted every time the daemon
starts.

---

## 2. Daily operation

Nothing to start. `magnus-buttons` is a user service with lingering enabled, so
it comes up on power-on with nobody logged in.

**Power on → wait ~1 min → press RB.** The first minute is the robot's own audio
service booting; the daemon restarts in a loop until it answers, which is the
intended wait-for-ready mechanism, not an error.

Before pressing **R2**, check the arm has clear space and nobody is standing
within reach. R2 is the only button that moves the robot.

Buttons ignore a second press while the first action is still running, so
guests cannot stack two arm routines or talk over the greeting.

---

## 3. Checks and troubleshooting

Log in from a laptop on the neck cable (laptop IP `192.168.123.222`):

```bash
ssh unitree@192.168.123.164
```

### Is it alive?

```bash
systemctl --user status magnus-buttons -l
```

Healthy output ends with `ready — 3 button(s)` and `lowstate stream OK`.

> Use `systemctl --user status`, **not** `journalctl --user`. This unit ships
> without persistent journal files, so `journalctl --user` returns "No entries"
> on a perfectly healthy service.

### Symptom → cause

| Symptom | Cause | Fix |
| --- | --- | --- |
| No `lowstate stream OK` | Remote is off, or wrong interface | Power the remote on. A powered-off remote is **not** detectable from software — it is a physical check |
| Service restarting in a loop right after an edit | A Python 3.8 incompatibility (laptops run 3.11+) | See §6 |
| Button logs `finished` but nothing was heard | Audio went somewhere with no speaker attached | §4 — never trust exit codes for audio |
| Nothing at all after power-on | Lingering got turned off | `loginctl enable-linger unitree` |

### Restarting without a password

There is no passwordless sudo on this unit. Restart the user service directly:

```bash
systemctl --user restart magnus-buttons
```

---

## 4. Changing what it says or does

### A new spoken line

The firmware accepts **only** 16 kHz mono 16-bit WAV. Generate and master on the
laptop, in the repo:

```bash
say -v Ava -r 165 -o /tmp/line.aiff "Your new sentence here."
ffmpeg -y -i /tmp/line.aiff -af "highpass=f=100,acompressor=threshold=-28dB:ratio=8:attack=2:release=100:makeup=10,equalizer=f=2600:t=q:w=1.5:g=5,alimiter=limit=0.90" -ar 16000 -ac 1 -sample_fmt s16 voices/sparco_welcome.wav
python examples/voice.py --check voices/sparco_welcome.wav
```

That filter chain is not decoration. Raw TTS lands near **-25 LUFS**, which is
inaudible across a room with people talking in it; the chain brings it to about
**-12 dBFS mean**, roughly 2.5× the perceived loudness, with one clipped sample
in 60 000. Six other chains were measured and none beat it, so treat this as the
ceiling — past here you get distortion, not volume.

Then copy it over and **restart the daemon**:

```bash
scp voices/sparco_welcome.wav unitree@192.168.123.164:magnus/magnus-g1/voices/
ssh unitree@192.168.123.164 'systemctl --user restart magnus-buttons'
```

The restart is required: the daemon caches audio at startup, so an `scp` alone
leaves it playing the old line while the file on disk looks correct.

Verify by checksum, never by file size — re-mastering preserves the sample
count, so the byte size often does not change at all:

```bash
md5 -q voices/sparco_welcome.wav
ssh unitree@192.168.123.164 'md5sum magnus/magnus-g1/voices/sparco_welcome.wav'
```

### A different gesture

Available actions: `clap`, `face wave`, `hands up`, `heart`, `high five`,
`high wave`, `hug`, `left kiss`, `reject`, `release arm`, `right hand up`,
`right heart`, `right kiss`, `shake hand`, `two-hand kiss`, `x-ray`.

Edit `routines/sparco_wave.json`, then dry-run before letting anyone press it:

```bash
python examples/arm_dance.py --dry-run --routine routines/sparco_wave.json
```

**Every routine must end with `release arm`.** The G1 holds its last arm pose
indefinitely — a routine without it leaves the robot frozen mid-gesture in front
of guests. The loader appends one if you forget, but write it explicitly.

### Re-binding a button

`routines/buttons.json` hot-reloads in about a second — no restart, and a
malformed file is rejected while the previous mapping keeps running. Each button
takes exactly one of `play` (a WAV), `tts` (built-in voice), or `cmd` (a shell
command).

---

## 5. Installing on a NEW unit (the offline recipe)

`scripts/install_onboard.sh` assumes what the first robot happened to have. On
this one it failed at step 4/6, and the three fixes below each avoid needing
root. Expect to need all three on any fresh unit.

**First, SSH access.** A new robot rejects your key; the default password is
`123` and Howard (not Claude) types it once:

```bash
ssh-keygen -R 192.168.123.164     # a new unit has a different host key
ssh-copy-id unitree@192.168.123.164
```

**Fix 1 — no `python3-venv`.** The venv step dies on `ensurepip is not
available`, and installing the package needs sudo. Skip the venv; the system pip
installs into `~/.local`:

```bash
cd /home/unitree/magnus && rm -rf venv
```

**Fix 2 — no internet.** DNS fails, and `nmcli connection up` is refused without
polkit auth even for a saved network. Lend the robot the laptop's connection
through an SSH reverse tunnel, which needs no password on either side. Run an
HTTP proxy on the laptop at `127.0.0.1:8899`, then:

```bash
ssh -R 8899:127.0.0.1:8899 unitree@192.168.123.164
```

**Fix 3 — `CYCLONEDDS_HOME`.** It is the colcon workspace's `install/cyclonedds`
— the directory holding `lib/cmake/CycloneDDS` — **not** `install/`. Pointing at
the parent fails with a message that names the variable, which reads like the
variable is being ignored. On the robot, with the tunnel up:

```bash
export CYCLONEDDS_HOME=/home/unitree/cyclonedds_ws/install/cyclonedds
export LD_LIBRARY_PATH=$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH
cd /home/unitree/magnus/unitree_sdk2_python
python3 -m pip install --user --proxy http://127.0.0.1:8899 -e .
```

**Then kill the proxy before you test anything.** A passing test with the tunnel
still up proves nothing about a showroom that has no Wi-Fi.

**Fix 4 — no passwordless sudo.** Use the user unit rather than a system one:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/magnus-buttons.user.service ~/.config/systemd/user/magnus-buttons.service
systemctl --user daemon-reload
systemctl --user enable --now magnus-buttons
loginctl enable-linger unitree      # start at boot with nobody logged in
```

The unit file carries `CYCLONEDDS_HOME` and `LD_LIBRARY_PATH`. Without them the
daemon imports fine by hand and dies as a service — the most confusing failure
in this whole document.

### Acceptance

Do not call a unit done until all four hold:

1. `systemctl --user status magnus-buttons -l` ends in `ready` + `lowstate stream OK`
2. `ping 8.8.8.8` from the robot **fails**, and RB still speaks
3. `systemctl --user is-enabled` → `enabled`, and `loginctl show-user unitree -p Linger` → `yes`
4. A person physically pressed RB and R2 and **heard and saw** the result

---

## 6. Python 3.8 (the trap that bit twice)

The robot runs **3.8**; laptops run 3.11+. A return annotation like
`-> tuple[list[str], str]` is evaluated when the function is defined, so it
crash-loops the service on the robot while passing every test on the laptop.

Every module in `examples/` must start with:

```python
from __future__ import annotations
```

`tests/test_buttons.py` scans the directory for it. It originally listed the
modules by name, which is exactly why the same crash shipped a second time in a
file added later — if you add a guard like this, make it scan, not enumerate.

Before restarting the service after any code change, import it under the
robot's own interpreter:

```bash
cd /home/unitree/magnus/magnus-g1/examples && python3 -c "import button_trigger"
```

---

## 7. Audio: exit code 0 does not mean audible

On the first robot, RB was re-pointed at a USB audio adapter. Six presses logged
`finished` with no error and the robot made no sound: PulseAudio accepts a
stream into an output whose jack has nothing plugged in. The fallback never
fired because nothing threw.

- `paplay`/`pactl` exit 0 means *the server took the bytes*, never *someone
  heard it*. The only acceptance test for audio is a person confirming.
- Never re-point a working audio path at new hardware until sound has been
  confirmed from that hardware. Add the route alongside; do not replace.
- The two paths are not interchangeable: the **SDK/DDS** route reaches the
  robot's own speaker and needs no PulseAudio, no session and no network; the
  **Jetson's PulseAudio sinks** only reach things plugged into the Jetson. This
  unit has no USB audio devices at all, so the SDK route is the only one that
  makes sound.

Keep RB and R2 on the SDK route. That is what makes them work offline.
