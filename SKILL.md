---
name: video-verify
description: "核对层：用 ffprobe / ffmpeg / numpy 检查成片——帧数与时长、均匀抽帧拼图看画面、各时刻底色类型、响度（Integrated LUFS / LRA / 真峰值）、切点与音频起音的音画同步偏差、频谱图，给出 PASS/FAIL。当用户要'检查视频有没有问题''测响度''音画同步吗''验收/QC 成片''抽帧看看''视频发布前检查'等时触发；任何代码生成视频流程的最后一步也用本 skill，导出后不核对就交付是不允许的。"
---

# 成片核对层

目标：在交付前用数字和肉眼各过一遍。脚本测的是能量化的（帧数、响度、同步、底色），拼图和频谱图是给人看的——两者都要做。

## 上下游

- 上游：`ffmpeg-encode` 的 MP4；预期值来自 `headless-export` 的 `build/meta.json`（含页面 `SPEC.verify` 的切点与底色表）。没有 meta 也能用命令行参数给预期。
- 下游：不通过 → 回到对应层修（画面问题改 scenes.js 重渲那一段；响度改 `outGain` 或 `encode.py --gain`；同步偏差查 score.js 是否引用了同一个 `TL`）。

## 工作流

```bash
python3 <skill>/scripts/verify.py <dir>/out/name_web.mp4 --meta <dir>/build/meta.json
# 或手动给预期
python3 <skill>/scripts/verify.py in.mp4 --fps 30 --duration 30 --cues 8,10,12,21 --colors "0.05:dark,11:primary,17:light,29.9:black" --primary '#E2231A'
```
输出 `check_sheet.jpg`（均匀 15 帧拼图）与 `spectrogram.png` 到 meta 所在目录（或 `<视频目录>/verify/`）。**然后用 Read 打开两张图看**：文字有没有溢出/重叠、颜色是否协调、鼓点栅格是否规整、落点在不在预期位置——脚本测不出这些。

## 检查项与阈值

| 项 | 判据 | 不通过时 |
|---|---|---|
| 容器/编码 | h264 + aac（或按需） | 用 ffmpeg-encode 重编 |
| 帧数 / 帧率 / 时长 | 帧数 = 时长 × fps（`--step` 折算）、时长误差 < 0.1 s | 导出漏帧或编码 `-shortest` 截短了：查音频长度 |
| 底色 | dark 平均亮度 < 70；black < 8；light > 180；primary 与主色距离 < 90 | 场景时间对不上、白闪时刻落在检查点上 |
| 响度 | Integrated 在 [-18, -11] LUFS（可 `--lufs`），真峰值 ≤ -0.5 dBTP | 改 `SPEC.music.outGain`（每 0.1 ≈ 1.2 dB）或 `encode.py --gain` |
| 同步 | 每个切点 ±40 ms 内有 > 6 dB 的起音 | score.js 该切点没引用 `TL`，或切点上只有渐入的 pad 没有瞬态 |

`strongest onsets` 一行列出全片最强的 12 个起音，用来核对落点位置是否符合设计。

## 只有音频 / 只有画面

- 只有音频：`ffmpeg -i a.wav -filter:a ebur128=peak=true -f null -` 看 Summary；频谱 `ffmpeg -i a.wav -lavfi showspectrumpic=s=1920x540 spec.png`。
- 无音轨的视频：脚本自动跳过响度与同步，只做帧数/底色/拼图。

## 文件

```
scripts/verify.py    全部检查 + 拼图 + 频谱图（依赖 ffmpeg、python3 + numpy）
```
