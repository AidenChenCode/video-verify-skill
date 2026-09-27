#!/usr/bin/env python3
"""核对层：看画面、测响度、测同步。
用法
  python3 verify.py <video.mp4> [--meta build/meta.json] [--cues 8,10,12,21] [--colors "0.05:dark,11:primary,17:light,29.9:black"]
                    [--primary '#E2231A'] [--fps 30] [--duration 30] [--frames 900] [--out DIR] [--sheet 15] [--tol-ms 40] [--lufs -18,-11]
  --meta      从 headless-export 的 meta.json 读帧率/时长/帧数/verify 预期（cues、colors、primary）
  --cues      应有明显音频起音的时刻（秒）；每个都会检查最近起音是否在 ±tol 内
  --colors    各时刻底色类型：dark(平均亮度<70) / black(<8) / light(>180) / primary(与 --primary 距离<90)
输出 <out>/check_sheet.jpg（均匀抽 N 帧拼图）、<out>/spectrogram.png；退出码 0 = 全部通过
"""
import argparse, glob, json, os, re, subprocess, sys, wave
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('video'); ap.add_argument('--meta'); ap.add_argument('--cues'); ap.add_argument('--colors'); ap.add_argument('--primary')
ap.add_argument('--fps', type=float); ap.add_argument('--duration', type=float); ap.add_argument('--frames', type=int)
ap.add_argument('--out'); ap.add_argument('--sheet', type=int, default=15); ap.add_argument('--tol-ms', type=float, default=40); ap.add_argument('--lufs', default='-18,-11')
a = ap.parse_args()
MP4 = a.video
OUT = a.out or (os.path.dirname(os.path.abspath(a.meta)) if a.meta else os.path.join(os.path.dirname(os.path.abspath(MP4)), 'verify'))
os.makedirs(OUT, exist_ok=True)
fps, dur, frames, primary = a.fps, a.duration, a.frames, a.primary
cues = [float(x) for x in a.cues.split(',')] if a.cues else None
colors = None
if a.colors:
    colors = []
    for item in a.colors.split(','):
        t, kind = item.split(':'); colors.append({'t': float(t), 'kind': kind})
if a.meta:
    m = json.load(open(a.meta)); st = m.get('step') or 1
    fps = fps or m['FPS'] / st; dur = dur or m['DUR']; frames = frames or m['FRAMES'] // st
    v = m.get('verify') or {}
    if cues is None: cues = v.get('cues')
    if colors is None: colors = v.get('colors')
    primary = primary or m.get('primary')
lo_lufs, hi_lufs = (float(x) for x in a.lufs.split(','))

def run(cmd, binary=False): return subprocess.run(cmd, capture_output=True, text=not binary)
ok_all = True
def check(name, cond, detail=''):
    global ok_all; ok_all &= bool(cond); print(f"  [{'PASS' if cond else 'FAIL'}] {name}  {detail}")

print(f"== verify {MP4}")
p = run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels', '-of', 'json', MP4])
info = json.loads(p.stdout)
vs = next(s for s in info['streams'] if s['codec_type'] == 'video'); au = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
d = float(info['format']['duration']); num, den = vs['r_frame_rate'].split('/'); vfps = float(num) / float(den)
print(f"  video {vs['codec_name']} {vs['width']}x{vs['height']} {vfps:g} fps nb_frames={vs.get('nb_frames')} | audio {(au['codec_name'] + ' ' + au['sample_rate'] + ' Hz ' + str(au['channels']) + 'ch') if au else 'none'} | {d:.3f} s")
if fps: check(f'frame rate == {fps:g}', abs(vfps - fps) < 0.01, f"{vfps:g}")
if frames: check(f'frame count == {frames}', int(vs.get('nb_frames', 0)) == frames, vs.get('nb_frames'))
if dur: check(f'duration ≈ {dur:.2f} s', abs(d - dur) < 0.1, f"{d:.3f}")

# ---- 抽帧拼图
n = a.sheet; cols = 5 if n >= 10 else min(n, 4); rows = (n + cols - 1) // cols
for f in glob.glob(os.path.join(OUT, 'chk_*.jpg')): os.remove(f)
for i in range(n):
    run(['ffmpeg', '-y', '-v', 'error', '-ss', f"{(i + 0.5) * d / n:.3f}", '-i', MP4, '-frames:v', '1', '-vf', 'scale=480:-2', os.path.join(OUT, f'chk_{i:02d}.jpg')])
run(['ffmpeg', '-y', '-v', 'error', '-framerate', '1', '-i', os.path.join(OUT, 'chk_%02d.jpg'), '-vf', f'tile={cols}x{rows}', '-frames:v', '1', os.path.join(OUT, 'check_sheet.jpg')])
print(f"  contact sheet → {os.path.join(OUT, 'check_sheet.jpg')}  （请打开看）")

# ---- 底色核对
if colors:
    def mean_rgb(t):
        r = run(['ffmpeg', '-v', 'error', '-ss', f"{t:.3f}", '-i', MP4, '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], binary=True)
        return np.frombuffer(r.stdout, np.uint8).reshape(-1, 3).mean(0)
    prim = np.array([int(primary[1:3], 16), int(primary[3:5], 16), int(primary[5:7], 16)], float) if primary else None
    KIND = {'dark': lambda c: c.mean() < 70, 'black': lambda c: c.mean() < 8, 'light': lambda c: c.mean() > 180,
            'primary': lambda c: prim is not None and np.linalg.norm(c - prim) < 90}
    for item in colors:
        c = mean_rgb(item['t']); check(f"t={item['t']:.2f} is {item['kind']}", KIND[item['kind']](c), f"mean RGB = {np.round(c, 1)}")

# ---- 响度 / 同步 / 频谱
if au:
    p = run(['ffmpeg', '-i', MP4, '-filter:a', 'ebur128=peak=true', '-f', 'null', '-'])
    tail = p.stderr[p.stderr.rfind('Summary:'):]
    lufs = float(re.search(r'I:\s+(-?[\d.]+) LUFS', tail).group(1)); lra = float(re.search(r'LRA:\s+([\d.]+) LU', tail).group(1)); peak = float(re.search(r'Peak:\s+(-?[\d.]+) dBFS', tail).group(1))
    print(f"  loudness: integrated {lufs:.1f} LUFS · LRA {lra:.1f} LU · true peak {peak:.1f} dBTP")
    check(f'integrated loudness in [{lo_lufs:g}, {hi_lufs:g}] LUFS', lo_lufs <= lufs <= hi_lufs, f"{lufs:.1f}")
    check('true peak ≤ -0.5 dBTP', peak <= -0.5, f"{peak:.1f}")
    wav = os.path.join(OUT, 'verify_audio.wav')
    run(['ffmpeg', '-y', '-v', 'error', '-i', MP4, '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', wav])
    with wave.open(wav) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    hop, win = int(sr * 0.005), int(sr * 0.02); m = (len(x) - win) // hop
    idx = np.arange(m)[:, None] * hop + np.arange(win)[None, :]
    db = 20 * np.log10(np.sqrt((x[idx] ** 2).mean(1)) + 1e-6)
    onset = np.maximum(np.diff(db), 0); t_axis = (np.arange(len(onset)) + 1) * hop / sr
    peaks = [i for i in range(len(onset)) if onset[i] > 6 and onset[i] == onset[max(0, i - 24):i + 25].max()]
    strong = sorted(peaks, key=lambda i: -onset[i])[:12]
    print('  strongest onsets (s): ' + ', '.join(f"{t_axis[i]:.2f}(+{onset[i]:.0f}dB)" for i in sorted(strong, key=lambda i: t_axis[i])))
    for te in (cues or []):
        near = min(peaks, key=lambda i: abs(t_axis[i] - te)) if peaks else None
        delta = (t_axis[near] - te) * 1000 if near is not None else float('inf')
        check(f'sync cue @ {te:.2f} s', abs(delta) <= a.tol_ms, f"nearest onset Δ = {delta:+.0f} ms")
    os.remove(wav)
    run(['ffmpeg', '-y', '-v', 'error', '-i', MP4, '-lavfi', 'showspectrumpic=s=1920x540:legend=1:color=intensity:scale=log', os.path.join(OUT, 'spectrogram.png')])
    print(f"  spectrogram → {os.path.join(OUT, 'spectrogram.png')}")
else:
    print('  （无音轨：跳过响度与同步）')
print('== RESULT:', 'ALL PASS' if ok_all else 'SOME CHECKS FAILED')
sys.exit(0 if ok_all else 1)
