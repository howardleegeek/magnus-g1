# Onboard install — put the stack INSIDE the robot (laptop-free demos)

Goal: voice files + dance routines live on the G1's internal development
computer (PC2), so the robot performs **without a laptop attached**.

**Prerequisite (hard):** CHECKLIST-FIRST-SESSION completed — Gate 1 passed over
the cable. Never debug the stack and the onboard environment at the same time.

**What PC2 is:** the G1 EDU contains two computers — the motion-control
computer (locked, never touch) and a user-accessible Ubuntu development
computer. Per the developer docs it's reachable at **`192.168.123.164`**
(default login `unitree` / `123` — CHANGE THIS PASSWORD in step 2). Exact
IP/credentials can vary by firmware batch — confirm in the G1 developer guide
for your firmware if login fails.

---

## Step 1 — Reach PC2 (laptop still connected via the neck RJ45)

```bash
ssh unitree@192.168.123.164        # expect an Ubuntu shell prompt
uname -m                           # note the arch (x86_64 or aarch64)
python3 --version                  # need 3.8+
```

## Step 2 — Basic hygiene (once)

```bash
passwd                             # change the default password NOW
mkdir -p ~/magnus
```

## Step 3 — Copy the stack + voice files INTO the robot

From the laptop (repo root). PC2 usually has no internet access, so we push
everything rather than git-clone:

```bash
rsync -av --exclude .venv --exclude .git ./ unitree@192.168.123.164:~/magnus/magnus-g1/
rsync -av ../unitree_sdk2_python/ unitree@192.168.123.164:~/magnus/unitree_sdk2_python/
```

Re-running the same two commands later = how you "update the robot" (new
routines, new voice WAVs). The `voices/` folder is now physically inside the G1.

## Step 4 — Install on PC2

```bash
ssh unitree@192.168.123.164
cd ~/magnus
python3 -m venv venv && source venv/bin/activate
pip install -e ./unitree_sdk2_python pytest    # no internet? see note below
python -m pytest magnus-g1/tests/ -q           # expect: 14 passed — same gate as everywhere
```

> No-internet note: if pip can't download build deps, run `pip download` for
> the requirements on your laptop (matching PC2's arch from step 1) and rsync
> the wheels over, then `pip install --no-index --find-links ./wheels ...`.

## Step 5 — Run from INSIDE the robot

On PC2, the robot's own network interface (find it: `ip a` — the one carrying
`192.168.123.164`, typically `eth0`):

```bash
python magnus-g1/examples/voice.py eth0 --play magnus-g1/voices/intro.wav
python magnus-g1/examples/arm_dance.py eth0
```

**GATE O:** both work with the Ethernet cable UNPLUGGED from the laptop
(SSH over the robot's Wi-Fi, or start via step 6). The robot is now
self-contained.

## Step 6 — Laptop-free triggers (pick one)

**A. Phone SSH (recommended first):** install Termius (iOS/Android), connect to
PC2 over the robot's Wi-Fi, run the one command. Demo kit = robot + phone.

**B. Autostart on boot:** as root on PC2:

```ini
# /etc/systemd/system/magnus-demo.service
[Unit]
Description=Magnus G1 demo routine
After=network.target

[Service]
User=unitree
WorkingDirectory=/home/unitree/magnus
ExecStartPre=/bin/sleep 30
ExecStart=/home/unitree/magnus/venv/bin/python magnus-g1/examples/arm_dance.py eth0
Restart=no

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable magnus-demo    # runs ~30 s after every boot
# disable when not demoing: sudo systemctl disable magnus-demo
```

⚠️ Boot-autostart means the robot moves 30 s after power-on, every power-on.
Only enable for demo days; SPOTTER rules still apply — e-stop in hand.

---

## Safety & hygiene rules

1. PC2 only. Never modify the motion-control computer, its services, or system
   packages PC2 shipped with — our stack is self-contained in `~/magnus`.
2. E-stop discipline unchanged: laptop-free ≠ supervision-free.
3. The repo on GitHub stays the source of truth — edit there, rsync to robot.
   Never hand-edit files on PC2 (they'll be overwritten by the next rsync).
4. Log onboard installs/updates in docs/LOG.md like any session.
