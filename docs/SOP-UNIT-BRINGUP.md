# SOP — Implement magnus-g1 stack on a robot unit

**Scope:** take github.com/howardleegeek/magnus-g1 from repo to a working, voiced dance demo on a physical G1.
**First unit:** G1-01 (the Magnus Unitree G1 EDU) — see Unit Registry below.
**Roles:** OPERATOR (runs commands, holds e-stop) + SPOTTER (second person, watches robot, calls aborts). Solo sessions allowed ONLY for Phase C onward with robot in normal balanced mode (no low-level work solo, ever).

**Session rule:** one line in `docs/LOG.md` per session (date, unit, phase reached, result, issues). No log line = session didn't happen.

---

## Unit Registry

| Unit | Model | Serial | Firmware | Notes |
|---|---|---|---|---|
| G1-01 | G1 EDU | _fill on first session_ | _fill from app_ | unit #1 |

Record serial + firmware version (from the Unitree app) during Phase B — firmware version determines which `action_map` entries exist, and support tickets require the serial.

---

## Phase A — Pre-session prep (no robot needed, do the day before)

On the laptop that will plug into the G1:

```bash
git clone git@github.com:howardleegeek/magnus-g1.git && cd magnus-g1
python3 -m venv .venv && source .venv/bin/activate
git clone https://github.com/unitreerobotics/unitree_sdk2_python
pip install -e unitree_sdk2_python pytest
python -m pytest tests/ -q            # MUST be 41 passed — do not proceed on red
python examples/arm_dance.py --dry-run
```

Voice pack: generate any missing WAVs per `voices/lines.txt` header, then:

```bash
python examples/voice.py --check voices/intro.wav
```

Every clip should report `OK:` with its length. "1 chunk" is sent in a single
call; anything longer reports "N chunks (streamed)" and is *also* fine in a
routine — arm_dance streams it on a thread. Just give that move a `hold` long
enough to outlast the sentence, or the arm drops mid-word.

**GATE A:** tests green + dry-run OK + all voice files check clean per the rules above, on the session laptop itself.

---

## Phase B — Physical setup (~15 min)

1. Battery ≥ 60%. Robot on flat ground, 3 m clear radius, no glass/edges nearby.
2. Pair and TEST the remote: enter damping mode once — robot must go limp. This is the abort button for everything that follows.
3. Record serial + firmware into Unit Registry (Unitree app).
4. Ethernet laptop ↔ robot: the **RJ45 port at the back of the neck** (next to the
   USB-C port — that USB-C is a peripheral/debug port for the onboard PC, NOT the
   laptop connection). Laptop static IP `192.168.123.222/24`; MacBooks need a
   USB-C→Ethernet adapter on the laptop side.
5. Power robot to normal balanced-stand mode via the standard remote sequence.

**GATE B:** e-stop verified working + robot standing + `ping 192.168.123.161` clean.

**ABORT at any point in any phase:** damping mode on the remote → robot limp → assess → log.

---

## Phase C — Software bring-up (~10 min)

```bash
python examples/preflight.py            # must exit 0
python examples/preflight.py --actions  # dump this firmware's action names
```

If any action in `routines/demo.json` is missing from the dump: edit the JSON to the listed names, re-run `--dry-run`, continue. **No Python edits during a session** — if code changes are needed, end the session, fix, re-run tests, come back.

**GATE C:** preflight exit 0 + all routine actions present in the firmware's action_map.

---

## Phase D — Voice bring-up (~10 min)

In order, each is go/no-go:

```bash
python examples/voice.py <iface> --volume 60          # 1. volume API responds
python examples/voice.py <iface> --tts "系统测试"      # 2. built-in TTS audible
python examples/voice.py <iface> --play voices/intro.wav   # 3. WAV streaming audible & clear
```

No sound at step 2/3: check volume isn't 0, check the app's audio settings, retry once. Distorted at step 3: re-check the file (`--check`), then lower volume — do not "fix" by re-encoding on the session laptop; log it.

**GATE D:** TTS and WAV both audible and clean at demo volume for the room.

---

## Phase E — Full voiced routine (~15 min)

1. OPERATOR announces start; SPOTTER confirms clear radius.
2. `python examples/arm_dance.py <iface>`
3. Watch first run end-to-end without touching anything (unless abort).
4. Run **3× consecutively**. Any e-stop, fault code, or voice desync = not passed; fix via routine JSON only, or end session.
5. Film run #3 (landscape, clean background).

**GATE E:** 3 consecutive clean runs + video captured + LOG.md line written.
This is SOP-G1-DANCE Gate 1 — the unit is now demo-capable.

---

## Phase F — Handoff (same day, ~15 min)

1. Commit any routine-JSON edits made during the session (`git add routines/ docs/LOG.md`, conventional commit, push).
2. Update Unit Registry (serial/firmware) in this file, commit.
3. Walk the SPOTTER through running Phase E themselves from this document alone. If they can't, the SOP has a gap — fix the doc, not the person.

**GATE F:** second person completes a clean run unaided + repo reflects reality (no local-only edits).

---

## Failure escalation

- Same gate fails **2×** in a session → stop the session, log symptoms, do not improvise workarounds on hardware.
- Hardware fault suspected (joint noise, fault codes, thermal warnings) → damping, power down, photo of the app's fault screen, open Unitree EDU support ticket with serial.
- Firmware update offered by the app mid-session → decline; firmware changes happen deliberately at session start, never mid-session.
