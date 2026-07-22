# Showroom deploy — RB button → welcome message (Tier 1)

**Customer ask:** press **RB** on the wireless controller → robot plays
"Welcome to Sofa showroom. Enjoy exploring our new outdoor collection."
**Origin:** Calvin's forwarded `setup_voice_trigger.md` (2026-07-20). This stack
implements it production-grade: debounced, tested, config-driven, systemd-run.

## The one command (tomorrow, at the robot)

Prereqs: checklist Parts 1–2 done (robot standing, e-stop tested, cable in neck
RJ45, laptop IP `192.168.123.222`). Then:

```bash
./scripts/deploy_showroom.sh        # --dry-run to preview first
```

Steps it runs: onboard install (repo+SDK+voices → Jetson, tests pass inside)
→ mpg123 fallback (best-effort) → speaker check (you HEAR the welcome line)
→ `magnus-buttons` systemd service enabled + started → live RB test.
**Success = press RB, robot speaks. Service survives reboots and auto-restarts.**

## What Calvin asked vs what shipped

| Ask | Shipped |
|---|---|
| Error handling | Every action wrapped; bad config rejected at load AND on hot-reload (old config keeps running); audio errors can't kill the daemon; heartbeat warns if the remote goes silent |
| Debouncing | Press-EDGE detection (holding ≠ repeat) + per-button cooldown (default 1.5 s) + busy-guard (presses during playback ignored & logged) |
| "Program any script on the fly" | `routines/buttons.json`: any button → `play` (WAV) / `tts` (built-in voice) / `cmd` (any shell command). Edit or rsync the file — **hot-reloads in ~1 s, no restart** |
| ChatGPT chat (bonus) | Follow-up — needs a mic check on the Jetson first (`arecord -l`); design sketch at the bottom |

## Button map (current)

| Button | Action |
|---|---|
| **RB** | Welcome line (customer's exact text, `voices/showroom_welcome.wav`) |
| **LB** | TTS: "Hello! Thanks for visiting. Let me know if you'd like a tour." |

All 16 buttons mappable: R1/RB L1/LB R2/RT L2/LT A B X Y arrows START SELECT F1 F2.
⚠️ Some buttons have built-in robot functions in normal mode — RB/LB are safe
choices; test any new binding for double-meaning before the customer sees it.

## Operations (after tomorrow)

- **Watch it live:** `ssh unitree@192.168.123.164 "sudo journalctl -u magnus-buttons -f"`
- **Change a binding on site, no laptop repo needed:** edit
  `/home/unitree/magnus/magnus-g1/routines/buttons.json` on the Jetson → auto-reload.
  ⚠️ On-site edits are TEMPORARY: the next `deploy_showroom.sh` rsync will
  overwrite them. Make anything permanent in the git repo (or scp the edited
  file back and commit) the same day.
- **New/changed voice line:** edit `voices/lines.txt` → `./scripts/build_voices.sh`
  → re-run `deploy_showroom.sh` (rsync is incremental, seconds).
- **WiFi so future visits are cable-free** (from Calvin's guide, optional):
  `ssh` in via cable once → `sudo nmcli device wifi connect "SSID" password "PASS"`
  → note `ip a | grep wlan` → next time SSH over WiFi, no cable.
- **Service control:** `sudo systemctl {status|restart|stop|disable} magnus-buttons`

## Fleet note (3-robot order)

Per-robot deploy = same one command against each unit; the only per-robot state
is `buttons.json` + WiFi config. Keep any customer-specific tweaks in git
(branch or per-unit config file) — never hand-edit only on a robot.

## Troubleshooting (merged: Calvin's guide + ours)

| Symptom | Fix |
|---|---|
| RB does nothing, no log line | Remote off/unpaired — daemon logs a heartbeat WARN after 10 s of silence |
| RB logs "ignored, audio still playing" | By design (busy-guard); wait for clip end |
| No sound, no errors | Volume: `voice.py <iface> --volume 85`; then `aplay -l` on Jetson — if "no soundcards", use AudioClient path only (already the default) |
| Service restart-looping | `journalctl -u magnus-buttons -n 50`; usual causes: wrong iface in the unit file (check `ip a` on Jetson) or SDK not installed in venv |
| Config edit didn't take | It was invalid — daemon logs `BAD CONFIG kept old mapping`; fix the JSON |

## ChatGPT-chat bonus (design sketch, not built)

Mic (`arecord`) → push-to-talk button in buttons.json (`cmd` → record 5 s)
→ Whisper/GPT API (needs Jetson internet or laptop relay) → reply via
`voice.py --tts`. Decision needed: API key handling + internet path on the
Jetson. Estimate: one desk day + one robot hour, after tomorrow's install.
