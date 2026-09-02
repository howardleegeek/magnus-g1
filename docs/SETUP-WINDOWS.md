# Windows setup — get this machine talking to the G1

Hand this file to a fresh Windows machine. It takes you from nothing to
"I can change what the robot says." Claude Code can run every step in it.

**You do not need WSL.** Everything runs *inside the robot*; this machine is a
terminal. Windows 10 (1809+) and 11 already ship the SSH client you need.

**What you're connecting to:** a Unitree G1 humanoid that greets visitors. A
button daemon runs on the robot's onboard computer, plays audio through the
robot's own speaker, and needs **no internet at all** — yours or the robot's.

| | |
| --- | --- |
| Jetson (PC2), where our code runs | `unitree@192.168.123.164` |
| Robot controller (PC1) | `192.168.123.161` |
| This machine's IP on the robot cable | `192.168.123.222` |
| Robot's first-login password | `123` (change it — see Step 3) |

---

## Step 0 — What to install first

```powershell
winget install --id Git.Git -e
winget install --id Gyan.FFmpeg -e          # only needed to make new voice lines
```

Close and reopen PowerShell afterwards so the new tools land on `PATH`. Claude
Code you presumably already have; if not, install it the same way you were told
to, then come back here.

Check SSH is present (it ships with Windows — no install):

```powershell
ssh -V
```

If that errors: **Settings → System → Optional features → Add → OpenSSH Client**.

---

## Step 1 — Plug in

Ethernet cable from this machine into the **RJ45 in the robot's neck**. Most
laptops need a USB-C-to-Ethernet adapter; any cheap one works.

The robot must be powered on. Its onboard services take about a minute after
power-up — that wait is normal and shows up later as warnings that clear on
their own.

---

## Step 2 — Give this machine a fixed IP

The robot's network hands out nothing, so set the address yourself. Find the
adapter first — the USB one usually shows as `Ethernet 2`:

```powershell
Get-NetAdapter | Where-Object Status -eq 'Up' | Format-Table Name, InterfaceDescription
```

Then, in **PowerShell as Administrator**, using that exact name:

```powershell
New-NetIPAddress -InterfaceAlias "Ethernet 2" -IPAddress 192.168.123.222 -PrefixLength 24
```

If it says the address already exists, it's already set — carry on. To change it
later, `Remove-NetIPAddress -InterfaceAlias "Ethernet 2" -Confirm:$false` first.

Confirm you can see the robot:

```powershell
ping 192.168.123.164
```

Replies mean the cable and the address are both good. No replies: check the
adapter name you used, that the cable is in the *neck* port, and that the robot
is on.

---

## Step 3 — Get in

Make a key, if this machine has none:

```powershell
ssh-keygen -t ed25519 -C "$env:COMPUTERNAME"
```

Press Enter through the prompts. Now push it to the robot. Windows has no
`ssh-copy-id`, so do it in one line — this asks for the robot password (`123`)
once, and never again:

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh unitree@192.168.123.164 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

Test that it's passwordless now:

```powershell
ssh unitree@192.168.123.164 "hostname"
```

> **If the robot is new to you and SSH complains the host key changed**, that's
> a different robot at the same address, which is normal when units get swapped:
> `ssh-keygen -R 192.168.123.164`, then retry.

**Change the default password once per robot**, not once per laptop — `123` is
publicly documented and a showroom is a public place:

```powershell
ssh unitree@192.168.123.164 "passwd"
```

---

## Step 4 — Get the repo

The repo is public, so this needs no account and no setup:

```powershell
cd $env:USERPROFILE
git clone https://github.com/howardleegeek/magnus-g1.git
cd magnus-g1
```

If this machine has no internet, use the `magnus-g1.bundle` file handed out
with this document instead — it is the whole repo in one file:

```powershell
git clone .\magnus-g1.bundle magnus-g1
```

The repo has a `CLAUDE.md` at its root. Open Claude Code **in this folder** and
it picks that up automatically, which is what makes it useful here rather than
guessing.

---

## Step 5 — Prove it works

Three checks. All three must pass before you touch anything.

```powershell
ssh unitree@192.168.123.164 "systemctl --user status magnus-buttons -l" | Select-String "ready|lowstate"
```

Expect `ready — N button(s)` and `lowstate stream OK`.

> `lowstate stream OK` missing? The remote control is switched off. Software
> cannot detect that — it is a physical check. Turn the remote on and re-run.
>
> Use `systemctl --user status`, **not** `journalctl --user`. This robot has no
> persistent journal, so `journalctl` says "No entries" on a perfectly healthy
> service.

See what the buttons currently do:

```powershell
ssh unitree@192.168.123.164 "cat magnus/magnus-g1/routines/buttons.json"
```

Then press a button on the remote and confirm you **hear** it. That is the real
gate — see the audio warning below for why the logs alone don't count.

---

## Changing what the robot says

Three things have to happen, and skipping any one of them fails quietly.

**1. Make the clip.** Firmware accepts **only 16 kHz mono 16-bit WAV**. Windows
can synthesize that directly, offline, with no install:

```powershell
Add-Type -AssemblyName System.Speech
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.SelectVoice("Microsoft Zira Desktop")     # $s.GetInstalledVoices() to list
$s.Rate = -1
$s.SetOutputToWaveFile("$env:TEMP\raw.wav", $fmt)
$s.Speak("Your new sentence here.")
$s.Dispose()
```

Write "U.S." as `U S` in the text, or the synthesizer reads it as the word "us".

**2. Make it loud enough.** This is not optional polish. Raw TTS lands near
**−25 LUFS** — inaudible across a room with people talking in it. This chain
brings it to about **−12 dBFS**, roughly 2.5× the perceived loudness:

```powershell
ffmpeg -y -i "$env:TEMP\raw.wav" -af "highpass=f=100,acompressor=threshold=-28dB:ratio=8:attack=2:release=100:makeup=10,equalizer=f=2600:t=q:w=1.5:g=5,alimiter=limit=0.90" -ar 16000 -ac 1 -sample_fmt s16 voices\my_line.wav
```

Six chains were measured against each other; this one won. Past it you get
distortion, not volume.

**3. Copy it over and restart the daemon.**

```powershell
scp voices\my_line.wav unitree@192.168.123.164:magnus/magnus-g1/voices/
ssh unitree@192.168.123.164 "systemctl --user restart magnus-buttons"
```

The restart is **required**: the daemon caches audio at startup, so a copy alone
leaves it playing the old line while the file on disk looks correct.

Point a button at it:

```powershell
ssh unitree@192.168.123.164 "cd magnus/magnus-g1 && python3 scripts/set_button.py R1 play voices/my_line.wav"
```

That script edits one button and leaves every other one alone, which matters
because the live config gets edited by whoever is standing in front of the
robot — copying the repo's version over it silently deletes their work. It also
keeps a `.bak` and refuses a file that isn't there yet.

`buttons.json` hot-reloads in about a second — no restart needed for a mapping
change, and a malformed file is rejected while the old mapping keeps running.

Verify it actually landed, by checksum — **not** by file size, since re-mastering
preserves the sample count and the byte size often doesn't change:

```powershell
(Get-FileHash voices\my_line.wav -Algorithm MD5).Hash.ToLower()
ssh unitree@192.168.123.164 "md5sum magnus/magnus-g1/voices/my_line.wav"
```

---

## Writing code on this machine

The robot is the runtime; this machine is where you edit and where the tests
run. The loop:

**1. Edit and test locally.** The test suite needs no robot and takes under a
second:

```powershell
python -m pytest tests\ -q
python -m black examples\ tests\ scripts\
```

**2. Copy the changed file over.**

```powershell
scp examples\button_trigger.py unitree@192.168.123.164:magnus/magnus-g1/examples/
```

**3. Import it under the robot's own Python before restarting.** This is the
step that catches the 3.8 problem below, and skipping it means finding out via a
crash-looping service instead:

```powershell
ssh unitree@192.168.123.164 "cd magnus/magnus-g1/examples && python3 -c 'import button_trigger'"
```

**4. Restart, then read the log.**

```powershell
ssh unitree@192.168.123.164 "systemctl --user restart magnus-buttons"
ssh unitree@192.168.123.164 "systemctl --user status magnus-buttons -l"
```

**5. Have someone press the button.** Not optional — see the audio warning.

You do **not** need the Unitree SDK on this machine. It only matters if you want
to drive the robot from the laptop, which nothing in the showroom setup does.
`docs/SETUP.md` covers that if you ever need it.

---

## Four things that will waste your afternoon

**Exit code 0 does not mean anyone heard it.** The audio layer accepts a stream
into an output with nothing plugged into it, so a press can log `finished` with
no error while the room hears silence — this happened for six presses in a row
once. **Only a person confirming counts.** Keep buttons on the robot's own
speaker; don't re-point audio at new hardware until sound has been confirmed
from it.

**The robot runs Python 3.8; your laptop runs 3.11+.** A modern type annotation
like `-> tuple[list[str], str]` is evaluated when the function is defined, so it
crash-loops the service on the robot while passing every test on your machine.
Every module in `examples/` starts with `from __future__ import annotations`.
After changing code, import it under the *robot's* interpreter before
restarting:

```powershell
ssh unitree@192.168.123.164 "cd magnus/magnus-g1/examples && python3 -c 'import button_trigger'"
```

**Arm routines must end with `release arm`.** The G1 holds its last pose
indefinitely, so a routine without it leaves the robot frozen mid-gesture in
front of guests. Dry-run before letting anyone press the button, and make sure
someone is watching the robot with the arm clear:

```powershell
ssh unitree@192.168.123.164 "cd magnus/magnus-g1 && python3 examples/arm_dance.py --dry-run --routine routines/<name>.json"
```

**There is no passwordless sudo on the robot.** Never reach for
`sudo systemctl` — the user unit restarts without it, which is why every command
above says `systemctl --user`.

---

## If you need to start the robot over

Full install path for a fresh unit — including the three ways the standard
installer fails (no `python3-venv`, no internet, no sudo) — is in
`docs/SOP-SPARCO-G1.md` §5. Read it before touching a new robot; those fixes are
not guesses, they're what actually worked.
