# Showroom deploy — RB button → welcome message (Tier 1)

**Customer ask:** press **RB** on the wireless controller → robot plays
"Welcome to Sofa showroom. Enjoy exploring our new outdoor collection."
**Origin:** Calvin's `setup_voice_trigger.md` (2026-07-20), rebuilt production-grade:
debounced + combo-safe, tested (41 tests), config-driven, systemd-run, and
adversarially verified (multi-agent review, 2026-07-20 night).

## Night-before gate (done at the desk — no robot)

- [ ] `python -m pytest tests/ -q` → all pass
- [ ] `./scripts/deploy_showroom.sh --dry-run` → full A–E plan prints, **no FAIL lines**
  (this catches the missing-SDK trap: it must print `SDK source: ...`)
- [ ] Laptop, Ethernet cable, USB-C adapter, charged remote, phone with app
- [ ] Print/save this doc's **Staff card** and **Open/Close checklist** sections

## The one command (at the robot)

Prereqs: robot standing, e-stop tested, cable in neck RJ45, laptop IP `192.168.123.222`.

```bash
./scripts/deploy_showroom.sh
```

Steps: onboard install (repo+SDK+voices+offline wheelhouse → Jetson, tests run
*inside* the robot) → interface auto-detected (eth0 vs eth1 varies by unit) →
speaker check (you HEAR the welcome) → `magnus-buttons` service installed with
the detected interface baked in → **gated live test**: press RB, script greps
the service journal for the play event and prints PASS/FAIL. Exit 0 = deployed.

**During install, also do once:** `ssh unitree@192.168.123.164 passwd` — change
the default password (`123`). G1s have a publicly documented BLE root exploit
(UniPwn) and known default creds; a public showroom is a hostile RF environment.

## Network map (never guess IPs on site)

| IP | What | Rule |
|---|---|---|
| 192.168.123.161 | Motion-control computer (PC1) | **Never touch, never SSH** |
| 192.168.123.164 | Jetson dev computer (PC2) | Our stack lives here, `~/magnus` only |
| 192.168.123.120/.20 | LiDAR (varies) | Leave alone |
| 192.168.123.222 | Your laptop (static) | — |

On PC2: **never kill or disable `master_service` / `vui_service`** (vui IS our
audio path) and never ServiceSwitch off `ai_sport`. Before any manual
`button_trigger.py` run: `systemctl status magnus-buttons` first — **never
double-launch** (two daemons = double audio + fighting logs).

## What Calvin asked vs what shipped

| Ask | Shipped |
|---|---|
| Error handling | Every action wrapped; ANY bad config (wrong types, NaN, arrays) rejected at load AND hot-reload with the old config kept running; audio errors can't kill the daemon; lowstate watchdog (never-arrived AND stopped cases) |
| Debouncing | Press-edge only + per-button cooldown (1.5 s) + **solo-grace guard**: a button fires only if held ALONE for 150 ms — the robot's own two-key combos (L1+A damping, R1+X motion, L2+R2 debug) can never trigger our audio. Busy-guard covers WAV **and** TTS duration |
| "Program any script on the fly" | `routines/buttons.json`: any button → `play`/`tts`/`cmd`. Edit or rsync → hot-reload in ~1 s, no restart, no re-fire of held buttons |
| ChatGPT chat (bonus) | Deferred by evidence: PC2 mic capture is broken in the SDK (returns all-zero data, issue #143) — needs an `arecord -l` check on real hardware first. Design: separate non-blocking path that fails to a canned local line; the RB→WAV core must stay fully offline |

## Button map (current)

| Button | Action |
|---|---|
| **RB** (alone, 150 ms) | Welcome line (`voices/showroom_welcome.wav`) |
| **LB** (alone, 150 ms) | TTS greeting |

`volume: 85` in buttons.json is asserted at daemon start and on every config
reload — survives power cycles and the Jetson's documented random reboots.

## ⚠️ Staff card (print, laminate, leave at the booth)

1. **E-stop = damping combo on the remote — CHECK THE FIRMWARE VERSION in the
   app and write the right combo here: V1.0.2 = L1+A · V1.0.4 = L2+B.**
   Damping makes the robot COLLAPSE — keep 1.5–2 m clear, never trigger it
   with a child inside the falling radius.
2. **Never press L2+R2** (debug mode): motion control dies and only a full
   reboot recovers. Symptom "remote seems dead" → suspect this → reboot robot.
3. **No firmware/OTA updates** the night before or during demo days — updates
   force joint recalibration, can change button combos, and have broken SDK apps.
4. Robot's built-in voice assistant shares our speaker: keep the robot offline
   or set the assistant to push-button mode so a visitor saying "Hello Robot"
   can't talk over the welcome clip. L1+SELECT force-interrupts its speech.
5. Robot stays behind the rope/plinth, ≥1 m standoff, signage up. Standing +
   powered ONLY with staff line of sight (kids shove robots; a shove on a
   balancing 35 kg humanoid is a fall).

## Open/Close checklist (staff, <2 min, no laptop) — assign a NAMED owner

**Open:** power on → wait for stable stand (~5 min budget) → remote ON (it
stays at the booth: it's the e-stop AND may be needed as keep-alive) → press
RB once → hear welcome = GREEN → battery ≥30%.
**Close:** power off per manual (short-press, then long-press >2 s) → remote
on charger → leave battery near 60–70%.
**Day rules:** stop demos at 10% battery; ~90-min battery rotation if swapping;
rest the robot damped/seated between bursts (sustained standing overheats
shoulder/hip actuators — the most common G1 hardware failure); charging only
during staffed hours, in view.

**First-day soak test (15 min, tomorrow):** leave ONLY our service running and
watch whether the G1's ~10-min idle auto-shutdown fires despite SDK traffic.
If it powers off: the bound remote staying ON at the booth is the keep-alive —
record the result in LOG.md either way.

## Operations (remote)

- Logs: `ssh unitree@192.168.123.164 "sudo journalctl -u magnus-buttons -f"`
- Rebind on site: edit `~/magnus/magnus-g1/routines/buttons.json` on the Jetson
  → hot-reload. ⚠️ TEMPORARY — commit to git same-day or the next deploy overwrites.
- New/changed voice line: `voices/lines.txt` → `./scripts/build_voices.sh` →
  re-run `deploy_showroom.sh` (incremental, seconds).
- Wi-Fi for cable-free visits: `sudo nmcli device wifi connect "SSID" password "PASS"`.

## Fleet rollout (3-robot order) — queued

Same one command per unit (interface auto-detected per robot). Per-unit state =
buttons.json + Wi-Fi, kept in git. Next upgrades, in order: (1) daily health
ping from each Jetson to Telegram (service active, last RB press, **presses/day
— the ROI number for the fleet order**); (2) nightly service-restart timer at
closing time (crash-restart can't see "running but deaf" states); (3) robots on
an isolated guest VLAN (UniPwn is wormable over BLE); (4) per-unit Vui_Service
version check (≥2.0.3.8) before first audio deploy.

## Troubleshooting

| Symptom | Fix |
|---|---|
| RB does nothing, no log line | **Remote-off is NOT detectable in logs** (lowstate flows regardless) — check the remote is ON, charged, bound (DL indicator). Then `--debug` run shows every key change |
| Log shows `WARN: no lowstate data` repeating | Wrong interface / DDS / robot off — re-run deploy (it re-detects the interface) |
| RB logs "ignored, audio still playing" | By design (busy-guard, now covers TTS too) |
| Welcome fires when operator uses remote combos | Should be impossible (solo-grace guard) — if seen, capture `--debug` log and file it |
| No sound, no errors | `GetVolume` probe line in startup log tells you if the audio service is dead (old Vui_Service) vs volume zero |
| Remote totally unresponsive | Suspect accidental L2+R2 debug mode → reboot robot |
| Service restart-looping | `journalctl -u magnus-buttons -n 50`; PC1 services take ~1 min after power-on — StartLimitIntervalSec=0 means it keeps retrying by design |
| Config edit didn't take | It was invalid — log shows `BAD CONFIG kept old mapping: <reason>` |
