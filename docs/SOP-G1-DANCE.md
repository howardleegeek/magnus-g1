# SOP — Unitree G1 EDU: from unboxed to dancing

**Owner:** Howard · **Robot:** G1 EDU · **Status:** v1.0 (2026-07-17)
**Rule:** every phase ends with a **GATE** — a checkable assertion. Do not start the next phase until the gate passes. If a gate fails twice, stop and reassess (do not brute-force retry).

Timeline at a glance:

| Phase | What | Time | Needs |
|---|---|---|---|
| 0 | Bench setup + first contact | half day | laptop, Ethernet cable |
| 1 | Arm dance demo (safe, high-level) | half day | Phase 0 |
| 2 | RL pipeline bring-up (sim only) | 2–4 days | GPU box (4090-class or cloud) |
| 3 | Whole-body dance (train → sim → gantry → free) | 1.5–3 weeks | Phase 2, gantry |
| 4 | Demo packaging (music, runbook, video) | 1–2 days | Phase 1 or 3 |

---

## Phase 0 — Bench setup + first contact (half day)

### Steps
1. **Charge & inspect**: battery ≥ 60%, joints free of shipping damage, e-stop remote paired and tested (press damping → robot goes limp on the stand).
2. **Network**: Ethernet from laptop to G1's port. Laptop static IP `192.168.123.222/24`. Verify:
   ```bash
   ping 192.168.123.161        # robot's onboard PC
   ```
3. **SDK install** (dev laptop):
   ```bash
   cd ~/work && python3 -m venv g1 && source g1/bin/activate
   git clone https://github.com/unitreerobotics/unitree_sdk2_python
   cd unitree_sdk2_python && pip install -e .
   ```
4. **First read** — subscribe to robot state (read-only, zero risk):
   ```bash
   python example/g1/low_level/g1_low_state_example.py <iface>   # exact example name per repo README
   ```
   Note your network interface name (`ifconfig` — the one holding 192.168.123.222).
5. **First command** — with robot in normal balanced-stand mode via remote, run the official high-level loco example; command a small in-place step.

### GATE 0 ✅
- [ ] `python examples/preflight.py` exits 0 (automates: ping, SDK install, action map)
- [ ] State topic prints live joint/IMU data
- [ ] One high-level command visibly executed (e.g., small velocity step) and stopped cleanly
- [ ] E-stop tested once during an active command — robot damps immediately

Failure handling: no ping → check link lights / IP subnet; state prints but commands ignored → robot not in the right mode (use remote to enter motion mode).

---

## Phase 1 — Arm dance demo (half day, safe)

High-level mode: onboard controller balances; we only sequence built-in arm actions.

### Steps
1. Clone this repo onto the dev laptop; list supported actions on YOUR SDK version:
   ```bash
   python examples/preflight.py --actions
   ```
2. Edit `routines/demo.json` (or copy it): set `bpm` to your track's BPM, arrange `moves` using only names from step 1. Validate offline:
   ```bash
   python examples/arm_dance.py --dry-run --routine routines/demo.json
   ```
3. Robot free-standing in a 3 m clear radius, e-stop in hand. Run:
   ```bash
   python examples/arm_dance.py <iface> --routine routines/demo.json
   ```
4. Iterate `beats` per move until it looks intentional, not robotic-pause-y (the script auto-appends `release arm` if you forget it).
5. Optional flourish: interleave `LocoClient` small rotations/steps between arm actions for a "turn and wave" effect — keep velocities ≤ 0.3 m/s indoors.

### Voice lines (part of Phase 1)

The G1 speaker takes **16 kHz mono 16-bit PCM WAV only**, streamed via the SDK's
`AudioClient` (or its built-in TTS for quick tests).

1. Write script lines in `voices/lines.txt`; generate WAVs per its header
   (edge-tts or macOS `say`, then the ffmpeg convert line).
2. Validate offline: `python examples/voice.py --check voices/<name>.wav`
   — routine clips must report "1 chunk (routine-safe)" (< 3 s).
3. Standalone test on robot: volume then a file:
   `python examples/voice.py <iface> --volume 85`
   `python examples/voice.py <iface> --play voices/intro.wav`
4. In routines, attach to a move: `"say": "voices/intro.wav"` (file) or
   `"tts": "text"` (built-in voice). Voice fires as the move starts.
5. Abort mid-audio: `python examples/voice.py <iface> --stop`.

### GATE 1 ✅
- [ ] Full routine runs 3× consecutively, no e-stop, no fault codes
- [ ] Voice line plays in sync with its move (volume set for room size)
- [ ] Ends with `release arm` every time
- [ ] 60-sec phone video recorded → drop in Magnus demo assets

**You now have a shippable demo.** Phases 2–3 are the upgrade path, not a blocker.

---

## Phase 2 — RL pipeline bring-up, sim only (2–4 days)

Goal: prove the train→deploy toolchain on a GPU box using a small example BEFORE touching the big dance framework. No robot needed this phase.

### Steps
1. **GPU box**: 1× RTX 4090-class (Ubuntu 22.04, driver ≥ 535) or cloud A100 (Lambda/SkyPilot). Isaac Gym/Lab requires NVIDIA — Mac won't work.
2. **Warm-up repo** — small, readable, end-to-end:
   ```bash
   git clone https://github.com/mujocolab/g1_spinkick_example   # train G1 spin kick with mjlab
   ```
   Follow its README: train the policy, replay it in the viewer.
3. **Sim2sim harness** — install [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco); confirm you can run a policy against the same DDS interface the real robot uses.
4. **Main framework** — clone [TeleHuman/PBHC](https://github.com/TeleHuman/PBHC) (KungfuBot) + Unitree's [LAFAN1 retargeted dataset](https://github.com/unitreerobotics/lafan1_retargeting_dataset). Run PBHC's install + their reference motion visualization to confirm the dataset loads.

### GATE 2 ✅
- [ ] Spin-kick (or equivalent) policy trained from scratch and replays cleanly in sim
- [ ] unitree_mujoco runs and accepts DDS commands
- [ ] PBHC environment installed; a LAFAN1 dance clip visualizes on the G1 model in sim

Failure handling: Isaac Gym install pain is normal — pin the exact Python/CUDA versions from PBHC's README; 2 failed attempts → switch to their Docker image if provided.

---

## Phase 3 — Whole-body dance (1.5–3 weeks)

### Steps
1. **Pick the clip**: one LAFAN1 dance segment, 20–40 s, moderate dynamics (no jumps for v1).
2. **Train** the PBHC tracking policy on it (hours per clip on a 4090). Train 2–3 seeds; keep the best by tracking reward.
3. **Sim2sim gate**: replay the checkpoint in unitree_mujoco. Pass = 10/10 runs no fall, joint torques within G1 limits.
4. **Real deploy — gantry** (EDU low-level):
   - Robot ON GANTRY, harness snug, 3 m clear, e-stop in hand, second person present.
   - Remote/app: **disable built-in motion service → debug mode** (skipping this = policy fights onboard controller, guaranteed violent shaking).
   - Run PBHC's deploy script over the wired link (never Wi-Fi for the 500 Hz loop).
   - First run at reduced speed/amplitude if the deploy script supports scaling.
5. **Iterate**: sim-real mismatch → check joint order/sign conventions between training env and `rt/lowstate` (the classic G1 deploy bug), then re-tune.
6. **Free-standing**: only after 5 consecutive clean gantry runs → slack the gantry (still attached) → 5 more clean runs → detach.

### GATE 3 ✅
- [ ] 10/10 clean sim2sim runs
- [ ] 5 consecutive clean gantry runs, then 5 slack-gantry runs
- [ ] Free-standing full dance, recorded on video, zero human intervention

Hard safety rules: never skip a stage; never test a new checkpoint free-standing; battery ≥ 40% for dynamic motions (voltage sag degrades torque).

---

## Phase 4 — Demo packaging (1–2 days)

1. Music sync: fixed countdown start (`3-2-1-play`) + script sleep offsets; don't over-engineer audio-reactive for v1.
2. Write the 1-page **demo runbook** (per MGL demo playbook style): pre-flight checklist, start command, abort procedure, reset procedure — so any Magnus/LSI person can run it.
3. Film a clean 60–90 s video (landscape, uncluttered background) for partner/investor use.

### GATE 4 ✅
- [ ] A person who is not you runs the full demo from the runbook alone, first try

---

## Escalation & cadence

- Any gate failed 2× → stop, write up symptoms, reassess approach (e.g., PBHC → BeyondMimic swap) — don't grind.
- Log each session's result (date, phase, gate status, issues) in `docs/LOG.md` — one line per session.
