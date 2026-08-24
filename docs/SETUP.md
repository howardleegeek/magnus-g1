# Team setup — install this stack on your machine

Follow top to bottom. **You are done when Step 5 prints `41 passed`.** Nothing
here needs the robot — robot sessions are a separate procedure
([SOP-UNIT-BRINGUP.md](SOP-UNIT-BRINGUP.md)).

## Step 0 — Access (ask Howard)

This repo is **private**. You need a GitHub account added as a collaborator —
send Howard your GitHub username. No access = nothing below works.

## Step 1 — Machine prerequisites

| OS | Status |
|---|---|
| Ubuntu 22.04 | ✅ best supported (Unitree's official target) |
| macOS | ✅ works; SDK install may need an extra step (see Troubleshooting) |
| Windows | ⚠️ use WSL2 + Ubuntu 22.04, then follow the Ubuntu path |

Need: Python 3.8+ (`python3 --version`), git, ffmpeg (`brew install ffmpeg` /
`sudo apt install ffmpeg`). ffmpeg is only needed if you'll make voice files.

## Step 2 — Clone

```bash
git clone https://github.com/howardleegeek/magnus-g1.git   # HTTPS — works with GitHub login
cd magnus-g1
```

(SSH clone also fine if you have keys set up.)

## Step 3 — Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # re-run this in every new terminal
pip install pytest
```

## Step 4 — Unitree SDK

```bash
git clone https://github.com/unitreerobotics/unitree_sdk2_python
pip install -e unitree_sdk2_python
```

## Step 5 — Verify (the done-when gate)

```bash
python -m pytest tests/ -q          # MUST print: 41 passed
python examples/arm_dance.py --dry-run   # prints the demo timeline
```

Both green → you're fully installed. Post in the team channel and you're
cleared to join a robot session as SPOTTER (see the bring-up SOP).

Note: the tests and dry-run pass even if Step 4 failed — they're robot-free by
design. Step 4 only matters for actual robot sessions, so if it fights you,
finish Step 5 first and fix the SDK before your first session.

## Troubleshooting

- **`git clone` asks for a password and rejects it** — GitHub needs a Personal
  Access Token or the `gh` CLI login (`gh auth login`), not your account password.
- **Step 0 forgotten** — a 404 on clone means you don't have repo access yet.
- **macOS: `pip install -e unitree_sdk2_python` fails on `cyclonedds`** — known
  issue; cyclonedds must be built from source on Mac. Follow the "install from
  source + CYCLONEDDS_HOME" section of the unitree_sdk2_python README, or just
  use an Ubuntu machine for robot sessions.
- **`ModuleNotFoundError: pytest`** — your venv isn't activated (Step 3, line 2).
- **Wrong Python** — some systems default `python3` to 3.7; install 3.10+
  (`brew install python@3.11` / `sudo apt install python3.11`).

## Second-unit gotchas (Sparco G1, Aug 2026)

`install_onboard.sh` assumes what the first robot happened to have. The second
one had none of it, so if a unit fails at step 4/6, check these in order:

- **`ensurepip is not available`** — the unit ships no `python3-venv`, and
  installing it needs sudo. Skip the venv: the system pip installs into
  `~/.local` with `pip install --user`, which needs no root at all.
- **`Temporary failure in name resolution`** — the robot has no internet, and
  `nmcli connection up` is refused without polkit auth. Neither is a blocker:
  run a local HTTP proxy on the laptop and reverse-tunnel it in, which needs no
  password on either side.

      ssh -R 8899:127.0.0.1:8899 unitree@192.168.123.164
      # on the robot: pip install --user --proxy http://127.0.0.1:8899 -e .

  Kill the proxy afterwards and re-verify — the robot must run fully offline.
- **`Could not locate cyclonedds`** — `CYCLONEDDS_HOME` is NOT the colcon
  workspace's `install/`; it is `install/cyclonedds`, the directory that
  actually contains `lib/cmake/CycloneDDS`. The same two vars must also be in
  the systemd unit or the daemon imports fine by hand and dies as a service.
- **No passwordless sudo** — use `deploy/magnus-buttons.user.service` plus
  `loginctl enable-linger unitree` instead of a system unit.
