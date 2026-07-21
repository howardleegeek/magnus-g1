# Unitree G1 机器人「说话+跳舞」上手 SOP（中文版）

> 代码仓库：github.com/howardleegeek/magnus-g1（私有，需 Howard 邀请你的 GitHub 账号）
> 效果：机器人自己开口说英文台词 + 完成 28 秒手臂舞蹈；最终可以装进机器人内部，脱离电脑演示。
> 任何时刻出问题：按遥控器的 **阻尼模式（damping）** = 急停，机器人立刻瘫软。

---

## 〇、准备清单

- [ ] GitHub 账号已被加为仓库协作者（发用户名给 Howard）
- [ ] 电脑：推荐 Ubuntu 22.04；Mac 也可以；Windows 用 WSL2
- [ ] 一根普通网线（RJ45）
- [ ] MacBook 需要 USB-C 转网口转接头（机器人插网线，不是插 USB-C）
- [ ] 遥控器充满电、手机装好宇树官方 App 并配对
- [ ] 机器人电量 ≥ 60%

---

## 一、装电脑环境（约 15 分钟，不需要机器人）

```bash
git clone https://github.com/howardleegeek/magnus-g1.git
cd magnus-g1
python3 -m venv .venv && source .venv/bin/activate
git clone https://github.com/unitreerobotics/unitree_sdk2_python
pip install -e unitree_sdk2_python pytest
python -m pytest tests/ -q
```

**✅ 完成标准：最后一条命令输出 `14 passed`。** 没有这个结果就是没装好
（常见原因见文末 FAQ）。装好后可先预览舞蹈时间轴（不用机器人）：

```bash
python examples/arm_dance.py --dry-run
```

---

## 二、第一次连接机器人（约 40 分钟）

### 物理连接
1. 机器人放平地，周围 **3 米内清空**，两人在场（一人操作、一人盯机器人）。
2. 开机、用 App/遥控器让机器人 **站稳**。
3. **先测急停**：按遥控器阻尼模式 → 机器人瘫软 → 重新站立。急停无效 = 今天到此为止。
4. 网线一头插电脑（转接头），另一头插 **机器人脖子后面的 RJ45 网口**
   （旁边那个 USB-C 口不是干这个的，别插）。
5. 电脑手动设 IP：`192.168.123.222`，子网掩码 `255.255.255.0`
   （Mac：系统设置 → 网络 → 转接头那个网卡 → IPv4 手动）。

### 联通检查
```bash
ping 192.168.123.161        # 通了(<2ms)说明连接成功
ifconfig                     # 找到 192.168.123.222 对应的网卡名，比如 en7
python examples/preflight.py # 期望：全部 [PASS]
```
下面把 `<网卡名>` 换成你查到的（如 en7 / eth0）。

### 让它说话
```bash
python examples/voice.py <网卡名> --volume 60
python examples/voice.py <网卡名> --tts "Hello, this is a test"   # 机器人开口说英文
python examples/voice.py <网卡名> --play voices/intro.wav          # 播放我们录好的台词
```

### 让它跳舞
```bash
python examples/arm_dance.py <网卡名>
```
机器人会边说边做：打招呼 →"Clap along with me!"→ 拍手 → 比心 → 举手 →
击掌 → 拥抱 → 挥手 → 收尾台词 "Thank you! Magnus Labs — robotics, deployed."

**✅ 完成标准：连续跑 3 遍全程无急停，第 3 遍拍视频。**

---

## 三、一键装进机器人（约 30 分钟，做完第二步再做）

装进去之后演示不再需要电脑，手机 SSH 一条命令即可触发。

网线保持连接，在仓库目录运行：

```bash
./scripts/install_onboard.sh
```

脚本自动完成：检查连接 → 把代码和语音文件推进机器人内部电脑 →
在机器人里面安装 → 在机器人里面跑同一套 14 项测试 →
**最后机器人自己开口说 "Hello! I'm the Magnus robot."** —— 听到这句 = 安装成功。

之后更新台词/舞蹈：改完文件重新跑一次这个脚本即可（增量同步，几秒钟）。

---

## 安全铁律（必须遵守）

1. 急停遥控器**永远拿在手里**，每次开工先测一次急停。
2. 同一步骤**失败 2 次就收工**，回来在电脑上解决，不要站在机器人旁边硬试。
3. 现场只允许改 `routines/*.json`（舞蹈编排），**不许现场改 Python 代码**。
4. 每次结束在 `docs/LOG.md` 记一行：日期 / 到哪一步 / 结果 / 问题。

---

## FAQ

- **git clone 报 404** → 你还没被加为协作者，找 Howard。
- **git 要密码但密码不对** → GitHub 需要用 token 或 `gh auth login`，不是账号密码。
- **Mac 装 SDK 报 cyclonedds 错误** → Mac 已知问题，按 unitree_sdk2_python 的
  README 源码编译，或直接换 Ubuntu 电脑（推荐）。
- **ping 不通** → 检查网线两头是否插紧、IP 是否设在**转接头网卡**上（不是 Wi-Fi）。
- **说话是中文不是英文** → 把 `routines/demo.json` 里 `tts_speaker` 改成另一个值（0/1 互换）。
- **想改台词** → 改 `voices/lines.txt` 一行文字，跑 `./scripts/build_voices.sh`，
  再跑一次第三步的安装脚本同步进机器人。
