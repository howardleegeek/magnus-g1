# G1 open-source community map (Jul 2026)

Where to ask questions, watch for new capabilities, and recruit. Channels marked
⚠️ are community-run/unofficial — verify the invite link before trusting binaries
or firmware advice from them.

## Official Unitree

| Channel | Use for |
|---|---|
| [G1 Developer Guide](https://support.unitree.com/home/en/G1_developer) (updated May 2026) | Canonical SDK/API docs, debug-mode procedures |
| [github.com/unitreerobotics](https://github.com/unitreerobotics) issues | SDK bugs — maintainers respond; search closed issues first, most deploy problems are already answered there |
| Unitree after-sales / EDU support (via support portal) | Hardware faults, firmware, warranty — EDU buyers get engineering support; use it |

## Robot-learning communities (Magnus's main lane)

| Community | Why it matters |
|---|---|
| **LeRobot Discord** (link on [github.com/huggingface/lerobot](https://github.com/huggingface/lerobot)) | The most active open robot-learning community; G1 is supported hardware; NVIDIA GR00T 1.7 landed in LeRobot workflows Jul 2026. Best place for teleop/IL/data-pipeline questions — exactly our MCAP lane. |
| **K-Scale Labs Discord** (link on [github.com/kscalelabs/kbot](https://github.com/kscalelabs/kbot)) | Open-source humanoid builders; strong hardware-hacker crowd |
| Isaac Lab / MuJoCo GitHub Discussions | Sim questions during Phase 2–3 |
| ⚠️ TheRoboVerse (theroboverse.com + Discord) | Largest unofficial Unitree owners community (grew out of Go2 hacking, covers G1); practical tips official docs won't give you |
| r/robotics, r/humanoidrobots | Low signal density but good for gauging what demos impress people |

## Labs that produce the G1 skill stack (follow their GitHub orgs)

| Lab | Output |
|---|---|
| **LeCAR Lab, CMU** (Guanya Shi) | ASAP, HumanoidVerse — sim2real agile skills |
| **Xiaolong Wang group, UCSD** | ExBody/ExBody2, AMO — expressive whole-body control |
| **Berkeley Hybrid Robotics** (Koushil Sreenath) | BeyondMimic — motion tracking |
| **NVIDIA GEAR** (Jim Fan, Yuke Zhu) | GR00T foundation models, SONIC behavior model |
| **TeleHuman / TeleAI** | PBHC "KungfuBot" — our chosen dance framework |
| **Stanford** (HumanPlus lineage) | Humanoid imitation from human data |
| **GalaxyGeneralRobotics** | OpenWBT Vision-Pro whole-body teleop |

Frontier watch (from [awesome-unitree-robots](https://github.com/shaoxiang/awesome-unitree-robots), Jul 2026): BFM-Zero (promptable behavior foundation model on G1), HumanX (skills from human videos, zero-shot sim2real), ResMimic/PILOT (loco-manipulation) — the field is moving from "dance" to "do useful work with hands", which is Magnus's actual business.

## Individuals worth following

- **Sentdex** (Harrison Kinsley) — [unitree_g1_vibes](https://github.com/Sentdex/unitree_g1_vibes) + YouTube series hacking a G1 from scratch; the best "developer experience" documentation of what owning one is like
- **Yanjie Ze** — maintains [awesome-humanoid-robot-learning](https://github.com/YanjieZe/awesome-humanoid-robot-learning); paper radar
- **@DrJimFan** (X) — GR00T/foundation-model direction; **@UnitreeRobotics** (X) — product/firmware announcements

## Chinese ecosystem

- **bilibili**: 宇树科技 official account + a deep pool of G1 二次开发 tutorial videos (search "G1 二次开发" / "G1 SDK") — often ahead of English content
- **知乎**: robotics columns cover G1 EDU teardowns and deploy write-ups
- **官方开发者群**: Unitree runs WeChat/QQ developer groups — ask after-sales support for an invite when confirming EDU support access
- **古月居 (guyuehome)**: main Chinese ROS community; G1 + ROS 2 tutorials

## How Magnus should engage (do / don't)

- **Do**: join LeRobot Discord (IL/data questions), file real issues on PBHC/OpenWBT when we hit deploy bugs (maintainers are responsive and it builds presence), mine Sentdex's series before our first low-level session.
- **Do**: watch BFM-Zero/GR00T-in-LeRobot — a promptable whole-body model would replace per-clip dance training entirely.
- **Don't**: post Magnus internal footage/details in public channels; ask questions with sanitized context (brand-independence discipline applies).
- **Don't**: run unofficial firmware/jailbreaks from community channels on our EDU unit — it's a support-contract asset.
