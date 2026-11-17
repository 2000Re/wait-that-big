"""通常動画(横 1920x1080)「True Size Challenge」を作る。週1本、12問。

Shorts と同じ地図・面積の計算・国を動かす処理・形の並べ方・声を使い、横長の画面用に組み直したもの。
問題は「どっちが大きい？(compare)」と「何個入る？(fit)」を交互に出す。

  0:00  導入  「Welcome to the True Size Challenge! 12 rounds, 5 seconds each. Keep score!」
  各問  問題を読む → 5秒のカウントダウン(左に数字と残り時間)→ 国を動かす/形を並べる → 答えと面積
  最後  「How many did you get right?」と点数の目安、チャンネル登録の呼びかけ

数字と国名は Shorts と同じく、すべて地図データから計算する(手で書いた答えはない)。
説明欄にチャプター(各問の開始時刻)を書く。サムネイル(1280x720)も作る。

使い方:
  python longform.py --tts dummy --rounds 2 --out out_long       試し(仮の声・2問だけ)
  python longform.py --history longform_history.json --out out_long   本番(meta.json も書く)
  python longform.py --upload --dir out_long --privacy unlisted       投稿して longform_history.json に記録
"""
import argparse
import json
import math
import random
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon

import catalog as K
import episodes as E
import geo
import media as M

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "longform_history.json"
SHORTS_HISTORY = ROOT / "upload_history.json"
TZ = ZoneInfo("Asia/Tokyo")
W, H, FPS = 1920, 1080, 30
SR = M.SR
ROUNDS = 12
THINK = 5.0                                  # 考える時間(秒)
PANEL = (0, 0, 620, H)                       # 左の文字の帯
PANEL_W = PANEL[2]
MAP_BOX = (660, 50, W - 40, H - 70)          # 地図の主役を収める範囲
SITE = "https://2000re.github.io/wait-that-big"
CHANNEL = "https://www.youtube.com/@wait-that-big"
NAVY = (8, 12, 24)


# ---------------------------------------------------------------- 横長の画面の部品


def text(lines, size, fill, bold=True, width=PANEL_W, shadow=200, spacing=1.15):
    return M.text_layer(lines, M.font(M.SANS_BOLD if bold else M.SANS, size), fill, width=width, spacing=spacing,
                        shadow=shadow)


def wrap(s, size, max_w, bold=True, max_lines=3):
    """左の帯の幅に収まるように折り返す。"""
    fnt = M.font(M.SANS_BOLD if bold else M.SANS, size)
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if fnt.getlength(t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:max_lines]


def base_map(view, colors=None, hide=(), equator=False):
    """動かない地図(横長)。media.base_map と同じ描き方で、画面全体に描く。"""
    colors = colors or {}
    img = Image.new("RGBA", (W, H), M.SEA + (255,))
    d = ImageDraw.Draw(img)
    step = 30 if view.k < 6 else 15 if view.k < 20 else 5
    lon0, _ = view.lonlat(0, 0)
    lon1, _ = view.lonlat(W, 0)
    for gx in range(int(math.floor(lon0 / step)) * step, int(lon1) + step, step):
        x, _ = view.xy(gx, 0)
        d.line([x, 0, x, H], fill=M.GRID + (255,), width=1)
    for gy in range(-75, 90, step):
        _, y = view.xy(0, gy)
        if 0 < y < H:
            d.line([0, y, W, y], fill=M.GRID + (255,), width=1)
    if equator:
        _, ye = view.xy(0, 0)
        if 0 < ye < H:
            d.line([PANEL_W, ye, W, ye], fill=(60, 80, 120, 255), width=3)
            d.text((W - 24, ye - 8), "Equator", font=M.font(M.SANS, 24), fill=(120, 140, 180, 255), anchor="rb")
    for f in geo.FEATS:
        name = f["properties"]["NAME"]
        if f["properties"]["CONTINENT"] == "Antarctica" or name in hide:
            continue
        col = colors.get(name, M.LAND)
        for ring in geo.rings(f["geometry"]):
            r = geo.unwrap(ring)
            mid = sum(lo for lo, _ in r) / len(r)
            shift = round((view.lon_c - mid) / 360) * 360
            d.polygon([view.xy(lo + shift, la) for lo, la in r], fill=col + (255,), outline=(20, 28, 44, 255))
    return img


def draw_shape(img, view, rs, col, alpha=230, outline=(255, 230, 200), outline_only=False, width=2):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for r in rs:
        pts = view.pts(r)
        if outline_only:
            d.line(pts + pts[:1], fill=col + (alpha,), width=3)
        else:
            d.polygon(pts, fill=col + (alpha,), outline=outline + (255,), width=width)
    img.alpha_composite(layer)


def panel_layer():
    """左の帯(半透明の紺)。地図の上に毎コマ重ねる。"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle(PANEL, fill=NAVY + (235,))
    shade = Image.new("RGBA", (40, H), (0, 0, 0, 0))
    for x in range(40):
        ImageDraw.Draw(shade).line([x, 0, x, H], fill=NAVY + (int(235 * (1 - x / 40)),))
    layer.alpha_composite(shade, (PANEL_W, 0))
    return layer


PANEL_LAYER = None
CREDIT = None


def chrome(img, round_no=None, total=ROUNDS):
    """左の帯・回の番号・出典を重ねる。"""
    img.alpha_composite(PANEL_LAYER)
    d = ImageDraw.Draw(img)
    d.text((PANEL_W / 2, 64), "TRUE SIZE CHALLENGE", font=M.font(M.SANS_BOLD, 30), fill=M.GOLD + (255,), anchor="mm")
    if round_no:
        d.text((PANEL_W / 2, 118), f"ROUND {round_no} / {total}", font=M.font(M.SANS_BOLD, 40),
               fill=M.WHITE + (255,), anchor="mm")
        # 進み具合の点
        x0 = PANEL_W / 2 - (total - 1) * 22 / 2
        for k in range(total):
            c = M.GOLD if k < round_no else (70, 80, 100)
            d.ellipse([x0 + k * 22 - 6, 156 - 6, x0 + k * 22 + 6, 156 + 6], fill=c + (255,))
    img.alpha_composite(CREDIT, (0, H - 44))


def countdown(img, t, start, end, y=820):
    """5・4・3・2・1 の数字と、減っていくバー。"""
    if not (start <= t < end + 0.3):
        return
    a = 1 - M.ease((t - end) / 0.3)
    left = max(0.0, end - t)
    d = ImageDraw.Draw(img)
    n = math.ceil(left) if left > 0 else 0
    if n:
        pulse = 1 + 0.12 * max(0.0, 1 - ((end - t) % 1) / 0.25) if left % 1 > 0.75 else 1.0
        d.text((PANEL_W / 2, y), str(n), font=M.font(M.SANS_BOLD, int(130 * pulse)), fill=M.GOLD + (int(255 * a),),
               anchor="mm", stroke_width=5, stroke_fill=NAVY + (255,))
    x0, x1, yb = 90, PANEL_W - 90, y + 100
    d.rounded_rectangle([x0, yb, x1, yb + 10], radius=5, fill=(255, 255, 255, int(60 * a)))
    frac = left / (end - start)
    if frac > 0:
        col = M.GOLD if frac > 0.3 else (235, 110, 90)
        d.rounded_rectangle([x0, yb, x0 + max(10, int((x1 - x0) * frac)), yb + 10], radius=5, fill=col + (int(255 * a),))


def answer_box(img, lines_big, lines_small, a, y=760):
    if a <= 0:
        return
    big = text(lines_big, 50, M.GOLD + (255,), shadow=230)
    small = text(lines_small, 30, (225, 230, 240, 255), bold=False, shadow=200)
    hgt = big.height + small.height + 50
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([40, y, PANEL_W - 40, y + hgt], radius=22, fill=(20, 28, 48, int(240 * a)),
                                            outline=M.GOLD + (int(200 * a),), width=3)
    img.alpha_composite(layer)
    img.alpha_composite(M.with_alpha(big, a), (0, y + 18))
    img.alpha_composite(M.with_alpha(small, a), (0, y + 18 + big.height + 6))


# ---------------------------------------------------------------- 1問(compare)


def round_compare(c, no, total, tts):
    a, b = c["a"], c["b"]
    sa, sb, va, vb = K.short(a), K.short(b), K.spoken(a), K.spoken(b)
    area_a, area_b = geo.area_km2(a), geo.area_km2(b)
    r = area_b / area_a
    dst = geo.centroid(b)
    a0 = [list(x) for x in geo.body(a)]
    a1 = geo.moved(a, dst)
    view = geo.View.fit([a0, geo.body(b), a1], MAP_BOX)
    base = base_map(view, colors={b: M.TARGET}, hide={a}, equator=True)

    lines = {
        "q": f"Round {no}. {K.cap(va)} or {vb}. Which one is bigger?",
        "move": f"Let's move {va} onto {vb}.",
        "ans": f"{K.cap(vb)} is about {E.times(r)} times bigger!",
    }
    clips, dur = M.say_all(tts, lines)
    at = {"q": 0.3}
    think = (at["q"] + dur["q"] + 0.2, at["q"] + dur["q"] + 0.2 + THINK)
    at["move"] = think[1] + 0.2
    move = (at["move"] + 0.2, at["move"] + 0.2 + max(2.6, dur["move"] + 0.4))
    at["ans"] = move[1] + 0.15
    end = at["ans"] + dur["ans"] + 2.2
    effects = [(M.sfx_pop(), 0.25)]
    effects += [(M.sfx_tick(), think[0] + k) for k in range(int(THINK))]
    effects += [(M.sfx_whoosh(), move[0]), (M.sfx_ding(), at["ans"])]

    q = text(["Which one is bigger?"], 44, M.WHITE)
    pills = [M.pill(sa, M.MOVER, w=440, dot=True), M.pill(sb, M.TARGET, w=440, dot=True)]
    right = M.pill(sb, M.TARGET, w=440, glow=True, dot=True)
    big = wrap(f"{sb} is {E.times(r)}× bigger!", 50, PANEL_W - 120)
    small = [f"{sb}: {E.fmt_area(area_b)}", f"{sa}: {E.fmt_area(area_a)}"]

    def frame(t):
        img = base.copy()
        e = M.ease((t - move[0]) / (move[1] - move[0]))
        if e > 0:
            draw_shape(img, view, a0, M.MOVER, alpha=160, outline_only=True)
        draw_shape(img, view, geo.moved(a, dst, e) if e > 0 else a0, M.MOVER)
        chrome(img, no, total)
        img.alpha_composite(q, (0, 220))
        rr = M.ease((t - at["ans"]) / 0.3)
        for k, pl in enumerate(pills):
            px, py = (PANEL_W - pl.width) // 2, 330 + k * 120
            if k == 1 and rr > 0:
                img.alpha_composite(M.with_alpha(pl, 1 - rr), (px, py))
                img.alpha_composite(M.with_alpha(right, rr), (px, py))
            else:
                img.alpha_composite(M.with_alpha(pl, 1 - 0.6 * rr), (px, py))
        countdown(img, t, think[0], think[1], y=650)
        answer_box(img, big, small, rr, y=600)
        return img

    return dict(lines=lines, clips=clips, at=at, effects=effects, end=end, frame=frame,
                chapter=f"{sa} or {sb}?", key=c["key"], thumb_t=think[0] + 1.0,
                answer=f"{sb} is about {E.times(r)}× bigger ({E.fmt_area(area_b)} vs {E.fmt_area(area_a)})")


# ---------------------------------------------------------------- 1問(fit)


def round_fit(c, no, total, tts, rng):
    big, small = c["big"], c["small"]
    sb, ss, plural, vb = K.short(big), K.short(small), K.C[small][2], K.spoken(big)
    area_b, area_s = geo.area_km2(big), geo.area_km2(small)
    n = round(area_b / area_s)
    choices, correct = E.fit_choices(n, rng)
    view = geo.View.fit([geo.body(big)], MAP_BOX, pad=0.05)
    base = base_map(view, colors={big: M.TARGET})
    main = max(geo.body(big), key=geo.ring_area_km2)
    inside = Polygon(view.pts(main)).buffer(0)
    copies = E._pack(view, inside, small, n)

    lines = {
        "q": f"Round {no}. How many {plural} fit inside {vb}? {choices[0]}, {choices[1]}, or {choices[2]}?",
        "fill": "Let's fill it up!",
        "ans": f"About {n} {plural}!",
    }
    clips, dur = M.say_all(tts, lines)
    at = {"q": 0.3}
    think = (at["q"] + dur["q"] + 0.2, at["q"] + dur["q"] + 0.2 + THINK)
    at["fill"] = think[1] + 0.2
    t_fill0 = at["fill"] + dur["fill"] + 0.1
    step = min(0.25, 4.0 / max(1, len(copies)))
    at["ans"] = t_fill0 + step * len(copies) + 0.3
    end = at["ans"] + dur["ans"] + 2.2
    effects = [(M.sfx_pop(), 0.25)]
    effects += [(M.sfx_tick(), think[0] + k) for k in range(int(THINK))]
    effects += [(M.sfx_pop(), t_fill0 + k * step) for k in range(len(copies))] + [(M.sfx_ding(), at["ans"])]

    q = text(wrap(f"How many {plural} fit inside {sb}?", 44, PANEL_W - 80), 44, M.WHITE)
    pills = [M.pill(ch, (200, 200, 210), w=300) for ch in choices]
    right = M.pill(choices[correct], (200, 200, 210), w=300, glow=True)
    centers = [(sum(x for p in cp for x, _ in p) / sum(len(p) for p in cp),
                sum(y for p in cp for _, y in p) / sum(len(p) for p in cp)) for cp in copies]
    cx_map = (MAP_BOX[0] + MAP_BOX[2]) / 2
    f_count = M.font(M.SANS_BOLD, 110)
    big_lines = [f"About {n} {plural}!"]
    small_lines = [f"{sb}: {E.fmt_area(area_b)}", f"{ss}: {E.fmt_area(area_s)}"]
    q_y = 210
    pills_y = q_y + q.height + 20

    def frame(t):
        img = base.copy()
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        shown = 0
        for k, cp in enumerate(copies):
            tk = t_fill0 + k * step
            if t < tk:
                continue
            shown += 1
            s = 1.3 - 0.3 * M.ease((t - tk) / 0.18)
            cx, cy = centers[k]
            col = M.MOVER if k % 2 == 0 else (255, 196, 90)
            for poly in cp:
                d.polygon([(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in poly], fill=col + (235,),
                          outline=(70, 30, 10, 255), width=2)
        img.alpha_composite(layer)
        if shown and t < at["ans"] + 0.3:
            ImageDraw.Draw(img).text((cx_map, H - 140), f"× {shown}", font=f_count, fill=M.MOVER + (255,),
                                     anchor="mm", stroke_width=6, stroke_fill=NAVY + (255,))
        chrome(img, no, total)
        img.alpha_composite(q, (0, q_y))
        rr = M.ease((t - at["ans"]) / 0.3)
        for k, pl in enumerate(pills):
            px, py = (PANEL_W - pl.width) // 2, pills_y + k * 105
            if k == correct and rr > 0:
                img.alpha_composite(M.with_alpha(pl, 1 - rr), (px, py))
                img.alpha_composite(M.with_alpha(right, rr), (px, py))
            else:
                img.alpha_composite(M.with_alpha(pl, 1 - 0.6 * rr), (px, py))
        countdown(img, t, think[0], think[1], y=pills_y + 3 * 105 + 90)
        answer_box(img, big_lines, small_lines, rr, y=pills_y + 3 * 105 + 30)
        return img

    return dict(lines=lines, clips=clips, at=at, effects=effects, end=end, frame=frame,
                chapter=f"How many {plural} fit in {sb}?", key=c["key"], thumb_t=t_fill0 + step * len(copies) * 0.7,
                answer=f"About {n} {plural} (by area: {sb} {E.fmt_area(area_b)} ÷ {ss} {E.fmt_area(area_s)})")


# ---------------------------------------------------------------- 導入と最後


def world_view():
    return geo.View(15, geo.merc_y(20), W / 360 * 1.05, (PANEL_W + W) / 2, H / 2)


def intro(tts, total):
    lines = {"hi": f"Welcome to the True Size Challenge! {total} rounds, {int(THINK)} seconds each. "
                   "Flat maps lie about size. Keep score, and let's see how many you get right!"}
    clips, dur = M.say_all(tts, lines)
    at = {"hi": 0.4}
    end = at["hi"] + dur["hi"] + 0.8
    base = base_map(world_view())
    t1 = text(["TRUE SIZE", "CHALLENGE"], 76, M.GOLD + (255,), spacing=1.05)
    t2 = text([f"{total} rounds · {int(THINK)} seconds each"], 34, M.WHITE + (255,), bold=False)
    t3 = text(["Keep score!"], 44, M.WHITE + (255,))

    def frame(t):
        img = base.copy()
        chrome(img)
        a = M.ease(t / 0.6)
        img.alpha_composite(M.with_alpha(t1, a), (0, 330))
        img.alpha_composite(M.with_alpha(t2, M.ease((t - 0.8) / 0.5)), (0, 540))
        img.alpha_composite(M.with_alpha(t3, M.ease((t - 1.6) / 0.5)), (0, 640))
        return img
    return dict(clips=clips, at=at, effects=[(M.sfx_whoosh(), 0.1)], end=end, frame=frame, chapter="Intro")


def outro(tts, total):
    lines = {"how": "How many did you get right? Tell me your score in the comments! "
                    "And subscribe for a new true-size quiz every day."}
    clips, dur = M.say_all(tts, lines)
    at = {"how": 0.4}
    end = at["how"] + dur["how"] + 2.5
    base = base_map(world_view())
    t1 = text(["How many did", "you get right?"], 60, M.WHITE + (255,), spacing=1.1)
    hi, mid = math.ceil(total * 0.8), math.ceil(total * 0.5)
    tiers = text([f"{hi}–{total}: Map master", f"{mid}–{hi - 1}: Globe trotter", f"0–{mid - 1}: Mercator fooled you"],
                 36, M.GOLD + (255,), spacing=1.5)
    t3 = text(["Tell me in the comments!"], 32, M.WHITE + (255,), bold=False)

    def frame(t):
        img = base.copy()
        chrome(img)
        img.alpha_composite(M.with_alpha(t1, M.ease(t / 0.5)), (0, 260))
        img.alpha_composite(M.with_alpha(tiers, M.ease((t - 0.8) / 0.5)), (0, 470))
        img.alpha_composite(M.with_alpha(t3, M.ease((t - 1.6) / 0.5)), (0, 760))
        return img
    return dict(clips=clips, at=at, effects=[(M.sfx_ding(), 0.2)], end=end, frame=frame, chapter="Your score")


# ---------------------------------------------------------------- 問題の選び方


RECENT_DAYS = 14        # この日数のうちに Shorts に出た国は、通常動画では使わない(足りなければ使う)


def recent_short_countries(shorts_history, now=None, days=RECENT_DAYS):
    """直近 days 日の Shorts に出てきた国・地域(比べる相手、overlay の端の国も含む)。"""
    now = now or datetime.now(timezone.utc)
    out = set()
    for h in shorts_history:
        try:
            t = datetime.fromisoformat(h["uploaded_at"])
        except (KeyError, ValueError):
            continue
        if (now - t).total_seconds() <= days * 86400:
            out |= K.shown_in(h)
    return out


def pick(n_rounds, shorts_history, long_history, rng, now=None):
    """compare と fit を交互に。次のものは避ける:
    - Shorts と過去の通常動画で出したお題(国の組み合わせ)
    - 直近 RECENT_DAYS 日の Shorts に出た国(候補が足りなくなった問だけ、この条件をゆるめる)
    - この動画の中で、すでに出した国"""
    used = {h["key"] for h in shorts_history} | {k for h in long_history for k in h.get("keys", [])}
    recent = recent_short_countries(shorts_history, now)
    pools = {}
    for fmt in ("compare", "fit"):
        cs = [c for c in K.CANDIDATES[fmt]() if c["key"] not in used]
        cs.sort(key=lambda c: -c["score"])
        pools[fmt] = cs
    chosen, seen, relaxed = [], set(), 0
    for i in range(n_rounds):
        fmt = "compare" if i % 2 == 0 else "fit"
        fresh = [c for c in pools[fmt] if not (K.countries_of(c) & seen) and c not in chosen]
        pool = [c for c in fresh if not (K.countries_of(c) & recent)]
        if not pool:
            pool, relaxed = fresh, relaxed + 1
        if not pool:
            raise SystemExit(f"{fmt} のお題が足りません")
        top = pool[:60]
        c = rng.choices(top, weights=[c["score"] for c in top])[0]
        chosen.append(c)
        seen |= K.countries_of(c)
    print(f"直近{RECENT_DAYS}日の Shorts に出た国: {len(recent)}"
          + (f"(候補が足りず、{relaxed}問はこの条件をゆるめた)" if relaxed else ""), flush=True)
    return chosen


# ---------------------------------------------------------------- 組み立て


def mix(segments):
    """各場面の声と効果音を、場面の開始時刻をずらして1本の音にする。"""
    total = sum(s["end"] for s in segments)
    n = int(math.ceil(total * SR)) + SR
    voice, fx = np.zeros(n, np.float32), np.zeros(n, np.float32)

    def put(buf, x, t):
        i = int(t * SR)
        x = x[: max(0, n - i)]
        buf[i:i + len(x)] += x
    t0 = 0.0
    for s in segments:
        for k, x in s["clips"].items():
            put(voice, x, t0 + s["at"][k])
        for x, t in s["effects"]:
            put(fx, x, t0 + t)
        t0 += s["end"]
    m = voice / max(1e-6, float(np.abs(voice).max())) * 0.8 + fx * 0.35
    m /= max(1.0, float(np.abs(m).max()) / 0.95)
    return m, total


def write_wav(path, m):
    pcm = (np.clip(np.stack([m, m], 1), -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def render(mp4, wav, segments, total):
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-i", str(wav), "-map", "0:v", "-map", "1:a", "-shortest",
                          "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    starts, t0 = [], 0.0
    for s in segments:
        starts.append(t0)
        t0 += s["end"]
    try:
        k = 0
        for f in range(int(round(total * FPS))):
            t = f / FPS
            while k + 1 < len(segments) and t >= starts[k + 1]:
                k += 1
            p.stdin.write(segments[k]["frame"](t - starts[k]).convert("RGB").tobytes())
            if f % (FPS * 30) == 0:
                print(f"  {t:.0f}/{total:.0f} 秒", flush=True)
    finally:
        p.stdin.close()
        if p.wait() != 0:
            raise RuntimeError("ffmpeg が失敗しました")
    return starts


def stamp(sec):
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def thumbnail(seg, number, path):
    """サムネイル(1280x720)。問題の途中のコマに、大きな題名を重ねる。"""
    img = seg["frame"](seg["thumb_t"]).convert("RGBA")
    ImageDraw.Draw(img).rectangle([0, 0, PANEL_W, H], fill=NAVY + (255,))
    t1 = text(["TRUE SIZE", "CHALLENGE"], 86, M.GOLD + (255,), spacing=1.0, shadow=255)
    t2 = text([f"#{number} · {ROUNDS} rounds"], 52, M.WHITE + (255,), shadow=255)
    t3 = text(["Can you beat", "the map?"], 64, M.WHITE + (255,), spacing=1.05, shadow=255)
    img.alpha_composite(t1, (0, 150))
    img.alpha_composite(t2, (0, 430))
    img.alpha_composite(t3, (0, 640))
    # 下の出典の行は小さくて読めないので、16:9 のまま下を切る(右も同じ割合だけ切る)
    img.convert("RGB").crop((0, 0, W - 96, H - 54)).resize((1280, 720), Image.LANCZOS).save(path, quality=90)


def description(number, rounds, starts):
    lines = [
        f"True Size Challenge #{number}: {len(rounds)} rounds of map questions. You get {int(THINK)} seconds each. "
        "Keep score and tell me how many you got right! 🌍",
        "",
        "Flat (Mercator) maps stretch land near the poles, so countries far from the equator look much bigger than "
        "they really are. In each round, a country is moved across the globe at its true size.",
        "",
        "Chapters:",
        f"{stamp(starts[0])} Intro",
    ]
    for i, (r, st) in enumerate(zip(rounds, starts[1:]), 1):
        lines.append(f"{stamp(st)} Round {i}: {r['chapter']}")
    lines.append(f"{stamp(starts[-1])} Your score")
    lines += ["", "Answers (spoiler!):"]
    lines += [f"{i}. {r['answer']}" for i, r in enumerate(rounds, 1)]
    lines += ["", "Areas are calculated on the WGS84 ellipsoid. Map data: Natural Earth (public domain).",
              "", f"Daily true-size Shorts: {CHANNEL}", f"Website: {SITE}/",
              "", "#maps #geography #truesize #mapquiz"]
    return "\n".join(lines)


def build(args):
    global PANEL_LAYER, CREDIT
    PANEL_LAYER = panel_layer()
    CREDIT = text(["Map data: Natural Earth (public domain) · Mercator projection · countries moved at true size"],
                  20, (170, 180, 200, 230), bold=False, width=W, shadow=160)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    hp = Path(args.history) if args.history else None
    long_history = json.loads(hp.read_text().strip() or "[]") if hp and hp.exists() else []
    shorts = json.loads(SHORTS_HISTORY.read_text()) if SHORTS_HISTORY.exists() else []
    number = max([h["number"] for h in long_history], default=0) + 1
    rng = random.Random(f"long:{number}:{args.seed or ''}")
    n_rounds = args.rounds or ROUNDS
    chosen = pick(n_rounds, shorts, long_history, rng)
    tts = M.make_tts(args.tts)
    print(f"#{number}: " + ", ".join(c["key"] for c in chosen), flush=True)

    rounds = []
    for i, c in enumerate(chosen, 1):
        print(f"  問題 {i}: {c['key']}", flush=True)
        rounds.append(round_compare(c, i, n_rounds, tts) if c["format"] == "compare"
                      else round_fit(c, i, n_rounds, tts, rng))
    segments = [intro(tts, n_rounds)] + rounds + [outro(tts, n_rounds)]
    m, total = mix(segments)
    wav = out / "audio.wav"
    write_wav(wav, m)
    print(f"動画を書き出しています({total:.0f} 秒)", flush=True)
    starts = render(out / "video.mp4", wav, segments, total)
    wav.unlink()
    thumb_seg = next((r for r in rounds if r["key"].startswith("fit:")), rounds[0])
    thumbnail(thumb_seg, number, out / "thumbnail.jpg")

    meta = {
        "number": number,
        "keys": [r["key"] for r in rounds],
        "date": datetime.now(TZ).date().isoformat(),
        "video": "video.mp4",
        "thumbnail": "thumbnail.jpg",
        "seconds": round(total, 1),
        "title": f"True Size Challenge #{number}: {n_rounds} Map Questions — Which Is Bigger? How Many Fit? 🌍"[:100],
        "description": M_yt(description(number, rounds, starts)),
        "tags": ["true size", "map quiz", "geography quiz", "mercator projection", "maps", "geography",
                 "true size of countries", "quiz"],
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(f"完了: {out / 'video.mp4'}({total:.0f} 秒)")
    print(meta["description"])


def M_yt(s):
    """YouTube はタイトル・説明文の < > を受け付けない。"""
    return s.replace("<", "‹").replace(">", "›")[:4900]


# ---------------------------------------------------------------- 投稿


THUMB_URL = "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={}"


def upload(args):
    import youtube_upload as Y
    out = Path(args.dir)
    meta = json.loads((out / "meta.json").read_text())
    hist_path = Path(args.history)
    history = json.loads(hist_path.read_text()) if hist_path.exists() else []
    if any(h["number"] == meta["number"] for h in history):
        raise SystemExit(f"投稿済みの回です: #{meta['number']}")
    token = Y.connect()
    res = Y.upload(token, out / meta["video"], meta, args.privacy)
    vid = res["id"]
    privacy = res.get("status", {}).get("privacyStatus", args.privacy)
    print(f"uploaded: https://youtu.be/{vid} ({privacy})")
    Y.set_output("video_id", vid)
    # サムネイル。チャンネルの電話番号確認が済んでいないと 403 になるので、失敗しても投稿は続ける
    thumb = out / meta.get("thumbnail", "thumbnail.jpg")
    if thumb.exists():
        try:
            Y.request(THUMB_URL.format(vid), data=thumb.read_bytes(), method="POST",
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
            print("thumbnail ok")
        except Exception as e:
            detail = e.read().decode(errors="replace")[:300] if hasattr(e, "read") else str(e)
            print(f"警告: サムネイルを設定できませんでした(YouTube Studio で設定してください): {detail}", file=sys.stderr)
    history.append({
        "number": meta["number"], "keys": meta["keys"], "date": meta["date"], "title": meta["title"],
        "seconds": meta["seconds"], "video_id": vid, "privacy": privacy,
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    hist_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--history", default=str(HISTORY), help="通常動画の投稿記録")
    ap.add_argument("--tts", choices=["google", "dummy"], default="google")
    ap.add_argument("--rounds", type=int, help=f"問題の数(既定 {ROUNDS}。試しに少なくするとき)")
    ap.add_argument("--seed", help="問題選びの乱数の種に足す文字(試し用)")
    ap.add_argument("--out", default="out_long")
    ap.add_argument("--upload", action="store_true", help="--dir の動画を投稿して記録する")
    ap.add_argument("--dir", default="out_long")
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    args = ap.parse_args()
    if args.upload:
        upload(args)
    else:
        build(args)


if __name__ == "__main__":
    main()
