# First robot session — field checklist (print this)

One page. Do steps in order. Every command shows what you SHOULD see — if you
see something else, stop and check the Troubleshooting line, don't improvise.

**ABORT at ANY moment:** press **damping** on the remote → robot goes limp. Then reassess.

---

## ☐ Bring (check before leaving your desk)

- ☐ Laptop with setup DONE: `python -m pytest tests/ -q` → **41 passed** (if not: docs/SETUP.md first)
- ☐ Ethernet cable (normal RJ45 network cable)
- ☐ USB-C → Ethernet adapter (MacBooks have no RJ45 port)
- ☐ Remote controller, charged
- ☐ Phone with Unitree app, paired to the robot
- ☐ Robot battery ≥ 60% (check in app)

---

## Part 1 — Physical setup (~10 min)

1. ☐ Place robot on flat ground, **3 m clear radius**, nothing fragile nearby.
2. ☐ Power on robot per manual; use app/remote to bring it to **balanced standing**.
   - ✅ Expect: robot standing steadily on its own.
3. ☐ **TEST THE E-STOP NOW**: press damping on the remote.
   - ✅ Expect: robot goes limp immediately. Re-stand it. (If damping didn't work, session over.)
4. ☐ In the app: write down **serial number + firmware version** → later goes in
   docs/SOP-UNIT-BRINGUP.md Unit Registry.
5. ☐ Plug Ethernet cable: laptop (via adapter) ↔ **RJ45 port at the BACK OF THE NECK**.
   - ⚠️ NOT the USB-C port next to it.

## Part 2 — Network (~5 min)

6. ☐ Set laptop IP manually — macOS: System Settings → Network → the USB adapter →
   Details → TCP/IP → Configure IPv4: **Manually** → IP `192.168.123.222`,
   Subnet `255.255.255.0` → OK.
7. ☐ Find the interface name: `ifconfig | grep -B 4 192.168.123.222` — the name
   at the top of that block (like `en7`) is your `<iface>` for every command below.
8. ☐ `ping 192.168.123.161`
   - ✅ Expect: replies, time < 2 ms. Ctrl-C to stop.
   - ❌ No reply → check cable seated both ends, check IP was applied to the ADAPTER not Wi-Fi.

## Part 3 — Software checks (~5 min)

```bash
cd magnus-g1 && source .venv/bin/activate
```

9. ☐ `python examples/preflight.py`
   - ✅ Expect: all `[PASS]`, ends "GATE 0 checks PASSED".
10. ☐ `python examples/preflight.py --actions`
    - ✅ Expect: a list of action names including: high wave, clap, heart,
      hands up, high five, hug, release arm.
    - ❌ Any missing → edit `routines/demo.json` to names that ARE listed,
      run `python examples/arm_dance.py --dry-run`, continue.

## Part 4 — Voice (~5 min)

11. ☐ `python examples/voice.py <iface> --volume 60`
    - ✅ Expect: prints "volume set to 60".
12. ☐ `python examples/voice.py <iface> --tts "Hello, this is a test"`
    - ✅ Expect: robot SPEAKS it, in an English voice.
    - ❌ Chinese voice → change `--speaker 1` to `--speaker 0` mapping: edit
      `tts_speaker` in routines/demo.json to the id that spoke English.
13. ☐ `python examples/voice.py <iface> --play voices/intro.wav`
    - ✅ Expect: robot says "Hello! I'm the Magnus robot. Watch this." clearly.
    - ❌ Silent/distorted → volume up/down first; log it; do NOT re-encode files here.

## Part 5 — The dance (~10 min)

14. ☐ Operator holds remote. Confirm 3 m radius clear. Robot standing.
15. ☐ `python examples/arm_dance.py <iface>`
    - ✅ Expect: voice line fires, then ~26 s of arm moves ending with arms released.
16. ☐ Run it **3× total**. All clean = **Gate 1 PASSED — demo-capable robot.**
17. ☐ Film the 3rd run (landscape).

## Part 6 — Wrap up (~5 min)

18. ☐ Add one line to `docs/LOG.md`: date | G1-01 | phase reached | result | issues.
19. ☐ Commit anything you edited: `git add routines/ docs/ && git commit -m "chore: first session results" && git push`
20. ☐ Unplug cable, power down robot per manual, charge remote + robot.

---

**Two-strike rule:** the same step fails twice → end session, log symptoms, fix at desk.
Never edit Python during a session — routine JSON only.
