# video-verify — 核对层 Claude Code Skill

> Verify layer of a code-generated video pipeline: ffprobe / ffmpeg / numpy checks on the finished file — frame count and duration, an evenly sampled contact sheet, background-tone checks at given times, loudness (integrated LUFS, LRA, true peak), cut-to-onset audio/video sync, and a spectrogram — with a PASS/FAIL summary.

技术栈五层里的**核对**层。数字交给脚本，画面交给眼睛：拼图和频谱图是给人看的，交付前两样都要过。

## 安装

```bash
git clone https://github.com/AidenChenCode/video-verify-skill.git ~/.claude/skills/video-verify
```
需要 ffmpeg / ffprobe、Python 3 + numpy。

## 使用

```bash
python3 ~/.claude/skills/video-verify/scripts/verify.py out/name_web.mp4 --meta build/meta.json
python3 ~/.claude/skills/video-verify/scripts/verify.py in.mp4 --fps 30 --duration 30 --cues 8,10,12,21 --colors "0.05:dark,11:primary,17:light,29.9:black" --primary '#E2231A'
```
输出 `check_sheet.jpg` 与 `spectrogram.png`；退出码 0 = 全部通过。

## 结构

```
SKILL.md             检查项、阈值、不通过时回到哪一层修
scripts/verify.py    全部检查 + 拼图 + 频谱图
```

## 同一套技术栈的其它 skill

| 层 | 仓库 |
|---|---|
| 画面 | [webgl-canvas-scene-skill](https://github.com/AidenChenCode/webgl-canvas-scene-skill) |
| 音乐 | [webaudio-score-skill](https://github.com/AidenChenCode/webaudio-score-skill) |
| 导出 | [headless-export-skill](https://github.com/AidenChenCode/headless-export-skill) |
| 编码 | [ffmpeg-encode-skill](https://github.com/AidenChenCode/ffmpeg-encode-skill) |
| 核对 | video-verify-skill（本仓库） |
| 组合体 | [motion-graphics-skill](https://github.com/AidenChenCode/motion-graphics-skill) |
