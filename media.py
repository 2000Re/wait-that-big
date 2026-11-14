"""見た目と音の部品: 文字、ボタン、地図の下地、読み上げ(Google Text-to-Speech)、効果音、動画の書き出し。"""
import base64
import io
import json
import math
import os
import subprocess
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import geo

HERE = Path(__file__).resolve().parent
SANS = HERE / "fonts" / "LiberationSans-Regular.ttf"
SANS_BOLD = HERE / "fonts" / "LiberationSans-Bold.ttf"
W, H, FPS = 1080, 1920, 30
SR = 48000

GOLD = (236, 200, 120)
WHITE = (250, 248, 240)
MOVER = (255, 150, 60)          # 動かす国
TARGET = (80, 150, 255)         # 比べる相手
LAND = (64, 72, 88)
SEA = (14, 22, 40)
GRID = (26, 38, 62)
SHADE_TOP = 432                 # 上の文字の帯(この下が地図)


def font(path, size):
    return ImageFont.truetype(str(path), size)


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def text_layer(lines, fnt, fill, width=W, spacing=1.18, shadow=200):
    lh = int(fnt.size * spacing)
    layer = Image.new("RGBA", (width, lh * len(lines) + 12), (0, 0, 0, 0))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(layer), ImageDraw.Draw(sh)
    for i, ln in enumerate(lines):
        y = i * lh + int(lh * 0.8)
        ds.text((width / 2, y + 3), ln, font=fnt, fill=(0, 0, 0, shadow), anchor="ms")
        d.text((width / 2, y), ln, font=fnt, fill=fill, anchor="ms")
    out = sh.filter(ImageFilter.GaussianBlur(5))
    out.alpha_composite(layer)
    return out


def fit_lines(text, path, max_w, sizes, max_lines=2):
    """幅に収まる大きさと改行を選ぶ。2行のときは、上下の行の長さがそろう位置で切る。戻り値: (行のリスト, フォント)"""
    words = text.split()
    for size in sizes:
        fnt = font(path, size)
        if fnt.getlength(text) <= max_w:
            return [text], fnt
        if max_lines >= 2:
            splits = [(" ".join(words[:k]), " ".join(words[k:])) for k in range(1, len(words))]
            splits = [sp for sp in splits if max(fnt.getlength(x) for x in sp) <= max_w]
            if splits:
                return list(min(splits, key=lambda sp: max(fnt.getlength(x) for x in sp))), fnt
    fnt = font(path, sizes[-1])
    k = max(1, len(words) // 2)
    return [" ".join(words[:k]), " ".join(words[k:])], fnt


def with_alpha(layer, a):
    if a >= 1:
        return layer
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * max(0.0, a))))
    return out


def pill(label, col, w=300, hgt=86, glow=False, size=40, dot=False):
    fnt = font(SANS_BOLD, size)
    while fnt.getlength(label) > w - (90 if dot else 40) and size > 24:
        size -= 2
        fnt = font(SANS_BOLD, size)
    im = Image.new("RGBA", (w + 20, hgt + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([10, 10, 10 + w, 10 + hgt], radius=hgt // 2,
                        fill=(GOLD if glow else (18, 20, 28)) + (240,), outline=col + (255,), width=5)
    cx = 10 + w / 2
    if dot:
        d.ellipse([36, 10 + hgt / 2 - 14, 64, 10 + hgt / 2 + 14], fill=col + (255,))
        cx += 18
    d.text((cx, 10 + hgt / 2), label, font=fnt, fill=(25, 20, 10, 255) if glow else WHITE, anchor="mm")
    return im


def timer_bar(img, t, start, end, x0=80, x1=1000, y=382):
    ta = 1 - ease((t - end) / 0.3)
    if ta <= 0:
        return
    left = 1 - min(1.0, max(0.0, (t - start) / (end - start)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x0, y, x1, y + 8], radius=4, fill=(255, 255, 255, int(60 * ta)))
    if left > 0:
        col = GOLD if left > 0.3 else (235, 110, 90)
        d.rounded_rectangle([x0, y, x0 + max(8, int((x1 - x0) * left)), y + 8], radius=4, fill=col + (int(255 * ta),))


def base_map(view, colors=None, hide=(), equator=False):
    """動かない地図。colors: {国名: 色}。hide に入れた国は描かない。"""
    colors = colors or {}
    img = Image.new("RGBA", (W, H), SEA + (255,))
    d = ImageDraw.Draw(img)
    step = 30 if view.k < 6 else 15 if view.k < 20 else 5
    lon0, _ = view.lonlat(0, 0)
    lon1, _ = view.lonlat(W, 0)
    for gx in range(int(math.floor(lon0 / step)) * step, int(lon1) + step, step):
        x, _ = view.xy(gx, 0)
        d.line([x, SHADE_TOP, x, H], fill=GRID + (255,), width=1)
    for gy in range(-75, 90, step):
        _, y = view.xy(0, gy)
        if SHADE_TOP < y < H:
            d.line([0, y, W, y], fill=GRID + (255,), width=1)
    if equator:
        _, ye = view.xy(0, 0)
        if SHADE_TOP < ye < H:
            d.line([0, ye, W, ye], fill=(60, 80, 120, 255), width=3)
            d.text((W - 24, ye - 8), "Equator", font=font(SANS, 24), fill=(120, 140, 180, 255), anchor="rb")
    lon_c = view.lon_c
    for f in geo.FEATS:
        name = f["properties"]["NAME"]
        if f["properties"]["CONTINENT"] == "Antarctica" or name in hide:
            continue
        col = colors.get(name, LAND)
        for ring in geo.rings(f["geometry"]):
            r = geo.unwrap(ring)
            # 画面の中心から見て、経度が近い側に描く(太平洋をまたぐ地図のため)
            mid = sum(lo for lo, _ in r) / len(r)
            shift = round((lon_c - mid) / 360) * 360
            d.polygon([view.xy(lo + shift, la) for lo, la in r], fill=col + (255,), outline=(20, 28, 44, 255))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([0, 0, W, SHADE_TOP], fill=(8, 12, 24, 235))
    img.alpha_composite(sh)
    return img


def draw_shape(img, view, rs, col, alpha=230, outline=(255, 230, 200), outline_only=False, width=2, clip=True):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in rs:
        pts = view.pts(r)
        if outline_only:
            d.line(pts + pts[:1], fill=col + (alpha,), width=3)
        else:
            d.polygon(pts, fill=col + (alpha,), outline=outline + (255,), width=width)
    if clip:
        ImageDraw.Draw(layer).rectangle([0, 0, W, SHADE_TOP], fill=(0, 0, 0, 0))   # 上の文字の帯には描かない
    img.alpha_composite(layer)


def band(img, y0, y1, a, x0=50, x1=W - 50):
    if a <= 0:
        return
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(8, 12, 24, int(220 * a)))
    img.alpha_composite(layer)


CREDIT = "Map data: Natural Earth (public domain) · Mercator projection"


# ---------------------------------------------------------------- 読み上げ

TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
DEFAULT_VOICE = "en-US-Chirp3-HD-Charon"
DEFAULT_RATE = 1.1


def read_wav(raw):
    if raw[:4] != b"RIFF":
        return np.frombuffer(raw[: len(raw) // 2 * 2], dtype=np.int16).astype(np.float32) / 32768
    with wave.open(io.BytesIO(raw)) as w:
        sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32) / 32768
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        t = np.arange(int(len(x) * SR / sr)) / SR
        x = np.interp(t, np.arange(len(x)) / sr, x).astype(np.float32)
    return x


def trim(x, thresh=0.01):
    idx = np.nonzero(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return x
    return x[max(0, idx[0] - int(0.02 * SR)): min(len(x), idx[-1] + int(0.06 * SR))]


class GoogleTTS:
    def __init__(self):
        # キーがなければヘッダーを付けずに送る(途中の proxy がキーを付ける環境のため)
        self.key = os.environ.get("GOOGLE_TTS_API_KEY")
        self.voice = os.environ.get("TTS_VOICE") or DEFAULT_VOICE
        self.rate = float(os.environ.get("TTS_RATE") or DEFAULT_RATE)

    def __call__(self, text):
        body = {"input": {"text": text},
                "voice": {"languageCode": "-".join(self.voice.split("-")[:2]), "name": self.voice},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": SR, "speakingRate": self.rate}}
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-Goog-Api-Key"] = self.key       # URL ではなくヘッダーで渡す(ログに残りにくい)
        req = urllib.request.Request(TTS_URL, data=json.dumps(body).encode(), method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Text-to-Speech が {e.code} を返しました: {detail}") from None
        return trim(read_wav(base64.b64decode(data["audioContent"])))


class DummyTTS:
    """通信なしの仮の声(試し用)。"""

    def __call__(self, text):
        words = text.split()
        dur = 0.15 + 0.3 * len(words)
        t = np.arange(int(dur * SR)) / SR
        env = 0.5 - 0.5 * np.cos(2 * np.pi * t * 3)
        return (np.sin(2 * np.pi * 180 * t) * env * 0.2).astype(np.float32)


def make_tts(name):
    return {"google": GoogleTTS, "dummy": DummyTTS}[name]()


def say_all(tts, lines):
    clips = {k: tts(v) for k, v in lines.items()}
    return clips, {k: len(v) / SR for k, v in clips.items()}


# ---------------------------------------------------------------- 効果音


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / decay)


def sfx_pop():
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    f = 900 * np.exp(-t * 18) + 500
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.03) * 0.5).astype(np.float32)


def sfx_tick():
    n = int(0.05 * SR)
    noise = np.convolve(np.random.default_rng(0).standard_normal(n), [1, -1], mode="same")
    return (noise * _env(n, 0.0005, 0.006) * 0.25).astype(np.float32)


def sfx_ding():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    x = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d)
            for f, a, d in [(1046.5, 0.5, 0.6), (1568.0, 0.3, 0.45), (2093.0, 0.15, 0.3), (2637.0, 0.08, 0.2)])
    return (x * np.minimum(1, t / 0.003) * 0.6).astype(np.float32)


def sfx_whoosh():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(1).standard_normal(n)
    out = np.empty(n)
    acc = 0.0
    for i in range(n):
        acc += (0.02 + 0.5 * (t[i] / t[-1]) ** 2) * (noise[i] - acc)
        out[i] = noise[i] - acc
    env = np.sin(np.pi * np.clip(t / 0.35, 0, 1)) ** 1.5
    return (out * env * 0.35).astype(np.float32)


def countdown_ticks(reveal):
    out, t = [], reveal - 3.0
    while t < reveal - 0.05:
        out.append((sfx_tick(), t))
        t += 0.5
    return out


def write_audio(path, end, clips, at, effects):
    """声(clips を at の時刻に)と効果音(effects: [(信号, 時刻)])を混ぜて WAV に書く。"""
    n = int(math.ceil(end * SR))
    voice, fx = np.zeros(n, np.float32), np.zeros(n, np.float32)

    def put(buf, x, t):
        i = int(t * SR)
        x = x[: max(0, n - i)]
        buf[i:i + len(x)] += x
    for k, x in clips.items():
        put(voice, x, at[k])
    for x, t in effects:
        put(fx, x, t)
    mix = voice / max(1e-6, float(np.abs(voice).max())) * 0.8 + fx * 0.35
    mix /= max(1.0, float(np.abs(mix).max()) / 0.95)
    pcm = (np.clip(np.stack([mix, mix], 1), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def save_thumb(img, path, width=360):
    """サイトの一覧に使う小さな 3:4 の JPEG(約30KB)。上の題名と下のクレジットを除いた、地図の部分を切り出す。"""
    box = (0, 440, W, 440 + W * 4 // 3)
    img.convert("RGB").crop(box).resize((width, width * 4 // 3), Image.LANCZOS).save(path, quality=80)


def render(mp4, wav, end, frame_at):
    """frame_at(t) が返す RGBA 画像を並べて、音と一緒に mp4 にする。"""
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-map", "0:v", "-map", "1:a", "-shortest",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    try:
        for f in range(int(round(end * FPS))):
            p.stdin.write(frame_at(f / FPS).convert("RGB").tobytes())
    finally:
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError("ffmpeg が失敗しました")
