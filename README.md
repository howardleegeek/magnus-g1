# magnus-g1

Magnus Labs — Unitree **G1 EDU** programming workspace. Control code, dance/demo choreography, and the curated map of the open-source G1 ecosystem.

> **Private repo.** Contains internal Magnus demo/ops material — do not open-source.

---

## 1. Hardware & access

| Item | Value |
|---|---|
| Robot | Unitree G1 **EDU** (low-level `rt/lowcmd` unlocked, secondary dev enabled) |
| Link | Ethernet to the robot's port; set your laptop to static IP `192.168.123.x/24` |
| Robot IP | `192.168.123.161` (default) |
| Middleware | DDS (CycloneDDS) — everything is pub/sub topics |
| SDKs | [`unitree_sdk2`](https://github.com/unitreerobotics/unitree_sdk2) (C++), [`unitree_sdk2_python`](https://github.com/unitreerobotics/unitree_sdk2_python) (Python), [`unitree_ros2`](https://github.com/unitreerobotics/unitree_ros2) |
| Docs | https://support.unitree.com (G1 developer guide) |

### Setup (dev laptop)

> Team members: follow [docs/SETUP.md](docs/SETUP.md) — full self-serve install
> with troubleshooting. Done when `pytest` prints 41 passed.

```bash
python3 -m venv .venv && source .venv/bin/activate
git clone https://github.com/unitreerobotics/unitree_sdk2_python
cd unitree_sdk2_python && pip install -e . && cd ..

# sanity check — read robot state
python unitree_sdk2_python/example/g1/high_level/g1_loco_client_example.py <iface>
```

### Control modes — the one concept that prevents broken robots

- **High-level**: robot's built-in controller keeps balance; you send velocity / gait / arm-action commands. Safe, works out of the box.
- **Low-level** (`rt/lowcmd` @ ~500 Hz): you command every joint; **you** own balance. Required for RL dance policies. Robot must be in **debug/damping mode** (built-in motion service OFF) or your commands fight the onboard controller.

---

## 2. Dance — two grades

### Grade A: arm choreography (day 1, safe)

The G1 ships with predefined arm actions (wave, clap, hug, high-five, heart, kiss…). Sequence them to music while the built-in controller balances/steps.

```bash
python examples/preflight.py                 # Gate 0 checks: network, SDK, action map
python examples/arm_dance.py --dry-run       # validate routine + print timeline (no robot needed)
python examples/arm_dance.py <iface>         # run it (default routine: routines/demo.json)
```

Choreography is data, not code: edit [`routines/demo.json`](routines/demo.json) — moves are timed in **beats at a BPM**, so pick your track's BPM and the routine stays on the music. `python examples/preflight.py --actions` lists valid action names.

### Grade B: whole-body dance / kungfu (RL, the impressive one)

Train a motion-imitation policy in simulation on retargeted human mocap, deploy via low-level. EDU unlocks this. Full runbook: [`docs/whole-body-dance.md`](docs/whole-body-dance.md).

Shortest path:
1. **Motions**: Unitree's official retargeted [LAFAN1 dance dataset](https://github.com/unitreerobotics/lafan1_retargeting_dataset) (includes dance clips, G1-ready).
2. **Training/deploy framework**: [PBHC / KungfuBot](https://github.com/TeleHuman/PBHC) (NeurIPS 2025, kungfu + dance on real G1) or [BeyondMimic](https://arxiv.org/html/2508.08241v3) (Berkeley, sim-to-real motion tracking on G1). Both publish deploy code.
3. **Sim2sim check** in [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) → then real robot **on the gantry**.

---

## 3. Open-source ecosystem map (curated, Jul 2026)

Mega-index: [awesome-unitree-robots](https://github.com/shaoxiang/awesome-unitree-robots) · [awesome-humanoid-robot-learning](https://github.com/YanjieZe/awesome-humanoid-robot-learning)

### Official (unitreerobotics)
| Repo | What |
|---|---|
| `unitree_sdk2` / `unitree_sdk2_python` | Core control SDKs (DDS) |
| `unitree_rl_gym` | RL locomotion baselines + sim2real deploy scripts |
| `unitree_mujoco` | MuJoCo sim with same DDS interface as real robot (sim2sim) |
| `avp_teleoperate` | Apple Vision Pro teleop for G1 arms/hands |
| `lafan1_retargeting_dataset` | Official retargeted human mocap incl. **dance** |
| `unitree_ros2` | ROS 2 bridge |

### Whole-body skills / dance (deploy-proven on G1)
| Repo | What | Difficulty |
|---|---|---|
| [TeleHuman/PBHC](https://github.com/TeleHuman/PBHC) (KungfuBot) | Highly-dynamic skills: kungfu, dancing; real G1 deploy | Hard (RL pipeline) |
| BeyondMimic | Guided-diffusion motion tracking, agile motions on G1 | Hard |
| [LeCAR-Lab/ASAP](https://github.com/LeCAR-Lab/ASAP) | Sim2real agile whole-body skills; PBHC builds on it | Hard |
| ExBody2 | Expressive whole-body control | Hard |
| [GalaxyGeneralRobotics/OpenWBT](https://github.com/GalaxyGeneralRobotics/OpenWBT) | Whole-body **teleop** via Vision Pro (real + sim) | Medium |
| [yifeichen2024/G1_deploy](https://github.com/yifeichen2024/G1_deploy) · [RoboMimicDeploy_G1](https://github.com/shanpenghui/RoboMimicDeploy_G1) | Community policy-deploy scaffolds for G1 | Medium |
| [mujocolab/g1_spinkick_example](https://github.com/mujocolab/g1_spinkick_example) | Train a double spin kick with mjlab — small, readable end-to-end example | Medium |

### Teleop / imitation learning / VLA (Magnus's strategic lane)
| Repo | What |
|---|---|
| [jiachengliu3/OpenWBC](https://github.com/jiachengliu3/OpenWBC) | VR teleop + data collection for whole-body VLA on G1 |
| [huggingface/lerobot](https://github.com/huggingface/lerobot) | Record → train (ACT/diffusion/VLA) → eval loop; G1 supported |
| [BlackOtters/SonicStar](https://github.com/BlackOtters/SonicStar) | Open G1 VLA stack w/ teleop data collection |
| NVIDIA Isaac **GR00T N1** (+ [g1-isaac-groot-n1](https://github.com/Jalil32/g1-isaac-groot-n1)) | Foundation-model route; GR00T-WholeBodyControl = RL lower body + IK upper body |

### Perception / navigation / sim
| Repo | What |
|---|---|
| [FAST_LIO_LOCALIZATION_HUMANOID](https://github.com/deepglint/FAST_LIO_LOCALIZATION_HUMANOID) | LiDAR localization for G1 |
| [go2_omniverse](https://github.com/abizovnuralem/go2_omniverse) | G1/Go2 in Isaac Lab / Isaac Sim |
| [linden713/humanoid_amp](https://github.com/linden713/humanoid_amp) | Isaac Lab AMP (style-based motion) for G1 |
| [GalacTechNyc/unitree-g1-autonomous](https://github.com/GalacTechNyc/unitree-g1-autonomous) | Autonomous visual navigation on G1 |
| [HansZ8/unitree_cpp](https://github.com/HansZ8/unitree_cpp) | Cable-free (Wi-Fi) G1 workflow |

---

## 4. Beyond dance — G1 capability menu for Magnus

| Capability | Stack | Magnus use |
|---|---|---|
| Choreographed demos (dance, greet, handshake, heart) | high-level SDK (this repo) | Partner/LSI/investor demos |
| Whole-body dance/kungfu | PBHC/BeyondMimic + LAFAN1 | Flagship demo moments |
| Teleop + data collection | OpenWBT/OpenWBC/avp_teleoperate | Feeds Magnus MCAP corpus — every operation hour = training data |
| Manipulation skills (pick/place/transport) | LeRobot IL on teleop data | Actual lab-automation tasks |
| Autonomous navigation | FAST-LIO + nav stack | Sample transport between benches |
| Voice/LLM interface | mic + ASR + LLM → high-level API | Guided demos, operator UX |

## 5. Safety (iron rules)

1. New policies / low-level code: **gantry first**, always.
2. Remote e-stop (damping) in hand for every run.
3. Sim (`unitree_mujoco`) → sim2sim → gantry → free-standing. Never skip a stage.
4. Clear 3 m radius; a falling G1 is ~35 kg.

## Showroom deployment (Tier 1 — the showroom)

RB button → welcome message, running as a systemd service inside the robot.
One command at the robot: `./scripts/deploy_showroom.sh`. Full doc:
[docs/SHOWROOM-DEPLOY.md](docs/SHOWROOM-DEPLOY.md).

## Repo layout

```
examples/   runnable scripts (preflight → arm_dance / voice / button_trigger)
routines/   demo.json (choreography) + buttons.json (button→action map) — data, not code
voices/     voice pack (lines.txt = source; scripts/build_voices.sh = builder)
scripts/    build_voices / install_onboard (one-shot) / deploy_showroom (one-shot)
deploy/     systemd units for the robot
docs/       SOPs: SETUP, CHECKLIST-FIRST-SESSION, SHOWROOM-DEPLOY, ONBOARD-INSTALL, SOP-CN …
```
