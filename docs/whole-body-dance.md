# Whole-body dance on G1 EDU — runbook

Goal: G1 performs full-body dance (legs + torso + arms) from retargeted human
mocap, via an RL motion-imitation policy. This is the Grade-B track from the
README. Budget realistically: **2–4 weeks** for a first clean routine if one
engineer owns it, mostly sim iteration.

## Pipeline overview

```
human mocap clip (dance)
  └─ retarget to G1 skeleton          ← skip: Unitree already did this (LAFAN1)
       └─ train tracking policy (Isaac Gym/Lab, PPO)     ← PBHC / BeyondMimic / ASAP
            └─ sim2sim validation (unitree_mujoco)
                 └─ real deploy, low-level rt/lowcmd, ON GANTRY
                      └─ free-standing performance
```

## Step 1 — motions

- Official, G1-ready: https://github.com/unitreerobotics/lafan1_retargeting_dataset
  (LAFAN1 mocap retargeted by Unitree to H1/H1-2/G1; includes dance sequences).
- Custom choreography later: retarget any AMASS/SMPL clip — see
  [G1-retarget](https://github.com/HomerIsAFool/G1-retarget) (PHC-based) or PBHC's
  retargeting tools. Even video-to-motion is viable (GEAR-SONIC/GMR route).

## Step 2 — pick a framework

| Framework | Pros | Cons |
|---|---|---|
| **PBHC (KungfuBot)** — github.com/TeleHuman/PBHC | Proven real-G1 dance/kungfu deploy, NeurIPS 2025, adaptive motion tracking | Heaviest setup (Isaac Gym) |
| **BeyondMimic** (Berkeley) | Very robust dynamic tracking, LAFAN1-native | Diffusion component adds complexity |
| **ASAP** — github.com/LeCAR-Lab/ASAP | Clean sim2real recipe, PBHC's base | Fewer dance-specific examples |
| **unitree_rl_gym** | Official, simplest | Locomotion-oriented, no expressive tracking |

Recommendation: **PBHC** — it is literally "make a G1 dance/kungfu" as a repo, and
its deploy code targets our exact robot.

## Step 3 — training

- GPU box needed (Isaac Gym/Lab): 1× RTX 4090-class is enough for single-motion
  tracking policies; cloud A100 via Lambda/SkyPilot also fine.
- Train per-clip tracking policy → checkpoint (~hours per motion, not days).

## Step 4 — sim2sim gate

Replay the policy in `unitree_mujoco` (same DDS interface as the real robot).
Pass criteria: no falls across 10 runs, joint torques within G1 limits.
**Do not skip** — this catches most sim2real breakage for free.

## Step 5 — real deploy (EDU low-level)

1. Robot on **gantry**, area clear, e-stop in hand.
2. App/remote: switch off the built-in motion service → debug mode.
3. Run the framework's deploy script (points at `rt/lowcmd`/`rt/lowstate`,
   500 Hz loop — use the C++ or compiled-Python deploy path, not naive Python).
4. First runs at reduced motion speed/amplitude if the framework supports scaling.
5. Only after repeated clean gantry runs → slack the gantry → free-standing.

## Failure modes to expect

- Policy fights onboard controller → you forgot debug mode (step 2).
- Robot shakes at 500 Hz → control loop jitter; run deploy on the robot's onboard
  PC or a wired real-time-ish host, never over Wi-Fi.
- Sim-perfect, real-fall → check `rt/lowstate` joint-order/sign conventions
  match the training env's; this is the classic G1 deploy bug.
