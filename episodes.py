"""3つの形式の動画を作る。どれも 1080x1920・30fps、声は Google Text-to-Speech。

各関数は動画(out/video.mp4)を書き、題名や説明に使う情報(dict)を返す。お題が成り立たないときは None を返す。
"""
import math

from PIL import Image, ImageDraw
from shapely.affinity import rotate
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import unary_union

import catalog as K
import geo
import media as M
from media import W, H

MAP_BOX = (40, 470, W - 40, 1390)     # 地図の主役を収める範囲(下は答えの帯のために空ける)
KICKER = "TRUE SIZE"
OUTRO = {"compare": "Which pair should we test next?", "fit": "What should we compare next?",
         "overlay": "Which country should we move next?"}


def place_name(ne_name):
    """画面に出す国名と、読み上げる国名。"""
    if ne_name in K.C:
        return K.short(ne_name), K.spoken(ne_name)
    long = geo.feature(ne_name)["properties"].get("NAME_LONG") or ne_name
    the = long.startswith(("United ", "Republic", "Central African", "Dominican", "Czech", "Democratic", "Gambia",
                           "Bahamas", "Solomon", "Maldives", "Comoros", "Marshall", "Faroe"))
    return long, ("the " if the else "") + long


TITLE_Y = 150


def header(title, kicker=KICKER):
    """(上の小見出し, 題名, 選択肢の y, 残り時間バーの y)。題名が2行なら、選択肢をその分下げる。"""
    lines, fnt = M.fit_lines(title, M.SANS_BOLD, W - 120, [64, 58, 54, 50])
    tl = M.text_layer(lines, fnt, M.WHITE, spacing=1.1)
    pill_y = max(262, TITLE_Y + tl.height - 2)
    return M.text_layer([kicker], M.font(M.SANS_BOLD, 30), M.GOLD), tl, pill_y, pill_y + 112


def times(r):
    """1.83 → '1.8'、7.4 → '7'。"""
    return f"{r:.1f}" if r < 3 else f"{round(r)}"


# ---------------------------------------------------------------- どっちが大きい？


def compare(c, tts, out, rng):
    a, b = c["a"], c["b"]
    sa, sb = K.short(a), K.short(b)
    va, vb = K.spoken(a), K.spoken(b)
    area_a, area_b = geo.area_km2(a), geo.area_km2(b)
    r = area_b / area_a
    app = geo.merc_area(geo.body(a)) / geo.merc_area(geo.body(b))
    src, dst = geo.centroid(a), geo.centroid(b)
    a0 = [list(x) for x in geo.body(a)]
    a1 = geo.moved(a, dst)
    view = geo.View.fit([a0, geo.body(b), a1], MAP_BOX)
    base = M.base_map(view, colors={b: M.TARGET}, hide={a}, equator=True)

    lines = {
        "q": f"{K.cap(va)} or {vb}. Which one is bigger?",
        "look": f"On this map, {va} looks bigger." if app >= 1.25 else "On this map, they look about the same.",
        "lock": "Lock in your answer!",
        "move": f"Now let's move {va} onto {vb}.",
        "ans": f"{K.cap(vb)} is about {times(r)} times bigger!",
        "why": "Flat maps stretch everything near the poles.",
        "outro": OUTRO["compare"],
    }
    clips, dur = M.say_all(tts, lines)
    at = {"q": 0.08}
    at["look"] = at["q"] + dur["q"] + 0.3
    at["lock"] = at["look"] + dur["look"] + 0.3
    reveal = at["lock"] + dur["lock"] + 1.8
    at["move"] = reveal
    move = (reveal + 0.3, reveal + 0.3 + max(3.0, dur["move"] + 0.6))
    at["ans"] = move[1] + 0.2
    at["why"] = at["ans"] + dur["ans"] + 0.35
    at["outro"] = at["why"] + dur["why"] + 0.4
    end = at["outro"] + dur["outro"] + 1.0
    effects = [(M.sfx_whoosh(), 0.0), *M.countdown_ticks(reveal), (M.sfx_whoosh(), move[0]), (M.sfx_ding(), at["ans"])]
    wav = out / "audio.wav"
    M.write_audio(wav, end, clips, at, effects)

    kicker, qmain, pill_y, timer_y = header("Which one is bigger?")
    pills = [M.pill(sa, M.MOVER, w=460, dot=True), M.pill(sb, M.TARGET, w=460, dot=True)]
    right = M.pill(sb, M.TARGET, w=460, glow=True, dot=True)
    big_lines, big_font = M.fit_lines(f"{sb} is {times(r)}× bigger!", M.SANS_BOLD, W - 160, [66, 58, 50])
    big = M.text_layer(big_lines, big_font, M.GOLD + (255,), shadow=230)
    stats = M.text_layer([f"{sb}  {fmt_area(area_b)}", f"{sa}  {fmt_area(area_a)}"], M.font(M.SANS_BOLD, 36),
                         (235, 235, 235, 255), shadow=220)
    credit = M.text_layer([M.CREDIT], M.font(M.SANS, 22), (170, 180, 200, 230), shadow=160)
    band_h = 110 + 70 * len(big_lines)

    def frame(t):
        img = base.copy()
        e = M.ease((t - move[0]) / (move[1] - move[0]))
        if e > 0:
            M.draw_shape(img, view, a0, M.MOVER, alpha=160, outline_only=True)    # もとの位置に輪郭を残す
        M.draw_shape(img, view, geo.moved(a, dst, e) if e > 0 else a0, M.MOVER)
        img.alpha_composite(kicker, (0, 110))
        img.alpha_composite(qmain, (0, TITLE_Y))
        rr = M.ease((t - at["ans"]) / 0.3)
        for k, pl in enumerate(pills):
            px = 60 + k * 500
            if k == 1 and rr > 0:
                img.alpha_composite(M.with_alpha(pl, 1 - rr), (px, pill_y))
                img.alpha_composite(M.with_alpha(right, rr), (px, pill_y))
            else:
                img.alpha_composite(M.with_alpha(pl, 1 - 0.6 * rr), (px, pill_y))
        M.timer_bar(img, t, 0.0, reveal, y=timer_y)
        if rr > 0:
            M.band(img, 1420, 1420 + band_h + 60, rr)
            img.alpha_composite(M.with_alpha(big, rr), (0, 1430))
            if t >= at["why"]:
                img.alpha_composite(M.with_alpha(stats, M.ease((t - at["why"]) / 0.4)), (0, 1430 + 70 * len(big_lines) + 30))
        img.alpha_composite(credit, (0, 1850))
        return img

    M.render(out / "video.mp4", wav, end, frame)
    return dict(
        title=f"{sa} or {sb}: which is bigger? 🌍",
        question=f"{sa} or {sb} — which one is bigger?",
        answer=f"{sb} is about {times(r)}× bigger ({fmt_area(area_b)} vs {fmt_area(area_a)}).",
        countries=[a, b], tags=[sa, sb], seconds=end, lines=lines)


def fmt_area(km2):
    return f"{km2 / 1e6:.2f} million km²" if km2 >= 1e6 else f"{km2 / 1e3:,.0f},000 km²"


# ---------------------------------------------------------------- 何個入る？


def _pack(view, inside, small, n):
    """small の形(その場所での本当の大きさ)を、inside(画面座標の多角形)の中に、重なりとはみ出しが少ない位置と向きで n 個置く。"""
    minx, miny, maxx, maxy = inside.bounds
    step = max(18.0, math.sqrt(inside.area / 600))
    cands = []
    y = miny + step / 2
    while y < maxy:
        x = minx + step / 2
        while x < maxx:
            if inside.contains(Polygon([(x - 1, y - 1), (x + 1, y - 1), (x + 1, y + 1), (x - 1, y + 1)])):
                cands.append((x, y))
            x += step
        y += step
    src = geo.centroid(small)
    rings = geo.compact_body(small)          # 何個入るかは面積(本体全体)で数え、並べる形は本島のまとまりだけ
    cache = {}
    placed, union = [], None
    for _ in range(n):
        best = None
        for (x, y) in cands:
            if (x, y) not in cache:
                m = geo.mover(src, view.lonlat(x, y))
                ps = [Polygon(view.pts(m(r))).buffer(0) for r in rings]
                ps = [g for p in ps for g in (p.geoms if hasattr(p, "geoms") else [p]) if g.area > 60]
                full = MultiPolygon(ps)
                cache[(x, y)] = (full, full.simplify(3))
            full, simp = cache[(x, y)]
            for ang in range(0, 180, 30):
                g = rotate(simp, ang, origin=(x, y))
                cost = g.difference(inside).area + (1.5 * g.intersection(union).area if union is not None else 0.0)
                if best is None or cost < best[0]:
                    best = (cost, (x, y), ang)
        _, xy, ang = best
        g = rotate(cache[xy][0], ang, origin=xy)
        placed.append([list(p.exterior.coords) for p in g.geoms])
        sg = rotate(cache[xy][1], ang, origin=xy)
        union = sg if union is None else unary_union([union, sg])
    return placed


def fit_choices(n, rng):
    shapes = [(0.5, 1, 1.8), (0.3, 0.6, 1), (1, 1.7, 2.8), (0.55, 1, 1.6)]
    for _ in range(20):
        f = rng.choice(shapes)
        vals = sorted({max(2, round(n * x)) for x in f})
        if len(vals) == 3 and n in vals:
            return [str(v) for v in vals], vals.index(n)
    return [str(max(2, n // 2)), str(n), str(n * 2)], 1


def fit(c, tts, out, rng):
    big, small = c["big"], c["small"]
    sb, ss, plural = K.short(big), K.short(small), K.C[small][2]
    vb = K.spoken(big)
    area_b, area_s = geo.area_km2(big), geo.area_km2(small)
    n = round(area_b / area_s)
    choices, correct = fit_choices(n, rng)
    view = geo.View.fit([geo.body(big)], MAP_BOX, pad=0.05)
    base = M.base_map(view, colors={big: M.TARGET})
    main = max(geo.body(big), key=geo.ring_area_km2)
    inside = Polygon(view.pts(main)).buffer(0)
    copies = _pack(view, inside, small, n)

    lines = {
        "q": f"How many {plural} fit inside {vb}?",
        "c": f"Is it {choices[0]}? {choices[1]}? Or {choices[2]}?",
        "lock": "Lock in your answer!",
        "fill": "Let's fill it up!",
        "ans": f"About {n} {plural}!",
        "outro": OUTRO["fit"],
    }
    clips, dur = M.say_all(tts, lines)
    at = {"q": 0.08}
    at["c"] = at["q"] + dur["q"] + 0.25
    at["lock"] = at["c"] + dur["c"] + 0.3
    reveal = at["lock"] + dur["lock"] + 1.8
    at["fill"] = reveal + 0.1
    t_fill0 = at["fill"] + dur["fill"] + 0.1
    step = min(0.28, 5.0 / max(1, len(copies)))
    at["ans"] = t_fill0 + step * len(copies) + 0.3
    at["outro"] = at["ans"] + dur["ans"] + 0.6
    end = at["outro"] + dur["outro"] + 1.0
    effects = [(M.sfx_whoosh(), 0.0), *M.countdown_ticks(reveal), (M.sfx_ding(), at["ans"])]
    effects += [(M.sfx_pop(), t_fill0 + k * step) for k in range(len(copies))]
    wav = out / "audio.wav"
    M.write_audio(wav, end, clips, at, effects)

    kicker, qmain, pill_y, timer_y = header(f"How many {plural} fit inside {sb}?")
    pills = [M.pill(ch, (200, 200, 210), w=220) for ch in choices]
    right = M.pill(choices[correct], (200, 200, 210), w=220, glow=True)
    f_count = M.font(M.SANS_BOLD, 120)
    big_txt = M.text_layer([f"About {n} {plural}!"], M.font(M.SANS_BOLD, 70), M.GOLD + (255,), shadow=230)
    note = M.text_layer([f"by area: {sb} {fmt_area(area_b)} ÷ {ss} {fmt_area(area_s)}"], M.font(M.SANS, 28),
                        (220, 225, 235, 255), shadow=200)
    credit = M.text_layer([M.CREDIT], M.font(M.SANS, 22), (170, 180, 200, 230), shadow=160)
    centers = [(sum(x for p in cp for x, _ in p) / sum(len(p) for p in cp),
                sum(y for p in cp for _, y in p) / sum(len(p) for p in cp)) for cp in copies]

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
            s = 1.3 - 0.3 * M.ease((t - tk) / 0.18)          # 少し大きく現れて、もとの大きさに
            cx, cy = centers[k]
            col = M.MOVER if k % 2 == 0 else (255, 196, 90)
            for poly in cp:
                d.polygon([(cx + (x - cx) * s, cy + (y - cy) * s) for x, y in poly], fill=col + (235,),
                          outline=(70, 30, 10, 255), width=2)
        img.alpha_composite(layer)
        img.alpha_composite(kicker, (0, 110))
        img.alpha_composite(qmain, (0, TITLE_Y))
        rr = M.ease((t - at["ans"]) / 0.3)
        for k, pl in enumerate(pills):
            px = 90 + k * 310
            if k == correct and rr > 0:
                img.alpha_composite(M.with_alpha(pl, 1 - rr), (px, pill_y))
                img.alpha_composite(M.with_alpha(right, rr), (px, pill_y))
            else:
                img.alpha_composite(M.with_alpha(pl, 1 - 0.6 * rr), (px, pill_y))
        M.timer_bar(img, t, 0.0, reveal, y=timer_y)
        if shown and t < at["ans"] + 0.3:
            ImageDraw.Draw(img).text((W / 2, 1520), f"× {shown}", font=f_count, fill=M.MOVER + (255,), anchor="mm",
                                     stroke_width=6, stroke_fill=(10, 14, 24, 255))
        if rr > 0:
            M.band(img, 1430, 1610, rr)
            img.alpha_composite(M.with_alpha(big_txt, rr), (0, 1440))
            img.alpha_composite(M.with_alpha(note, rr), (0, 1545))
        img.alpha_composite(credit, (0, 1850))
        return img

    M.render(out / "video.mp4", wav, end, frame)
    return dict(
        title=f"How many {plural} fit in {sb}? 🌍",
        question=f"How many {plural} fit inside {sb}?",
        answer=f"About {n} (by area: {sb} {fmt_area(area_b)} ÷ {ss} {fmt_area(area_s)}).",
        countries=[big, small], tags=[sb, ss], seconds=end, lines=lines)


# ---------------------------------------------------------------- 重ねてみる


def overlay_spot(c, rng):
    """行き先の地域の中で、日本などの両端がどちらも陸(しかも別々の国)に届く置き場所を探す。"""
    m = c["mover"]
    cx, cy = c["center"]
    found = []
    for dx in range(-8, 9, 2):
        for dy in range(-8, 9, 2):
            dst = (cx + dx, cy + dy)
            mv = geo.mover(geo.centroid(m), dst)
            p, q, km = geo.farthest_pair([mv(r) for r in geo.compact_body(m)])   # 端は本島のまとまりで測る(小さな離島は見えないので)
            (na, la), (nb, lb) = geo.country_at(*p), geo.country_at(*q)
            if la and lb and na != nb and m not in (na, nb):
                famous = (na in K.C) + (nb in K.C)
                found.append((-famous, abs(dx) + abs(dy), rng.random(), dst, p, q, km, na, nb))
    if not found:
        return None
    found.sort()
    return found[0][3:]


def overlay(c, tts, out, rng):
    m = c["mover"]
    sm, vm = K.short(m), K.spoken(m)
    spot = overlay_spot(c, rng)
    if spot is None:
        return None
    dst, p, q, km_exact, na, nb = spot
    if p[1] < q[1]:
        p, q, na, nb = q, p, nb, na                     # p = 北の端
    (sa, va), (sbn, vb) = place_name(na), place_name(nb)
    km = int(round(km_exact / 100) * 100)
    src = geo.centroid(m)
    final = geo.moved(m, dst)
    view = geo.View.fit([final], MAP_BOX, pad=0.2)
    base = M.base_map(view, hide={m})
    base_hi = M.base_map(view, colors={na: M.TARGET, nb: M.TARGET}, hide={m})
    # 最初の一枚から、飛んでくる形が画面の端に見えているように、動きの途中から始める
    frac0 = 0.0
    for i in range(100):
        f = i / 100
        xs = [x for r in geo.moved(m, dst, f) for x, y in view.pts(r) if M.SHADE_TOP < y < H]
        if xs and min(xs) < W - 60 and max(xs) > 60:
            frac0 = min(0.9, f + 0.09)
            break

    lines = {
        "q": f"What if we moved {vm} to {c['region_say']}?",
        "land": f"{K.cap(vm)} would stretch from {va}...",
        "land2": f"all the way to {vb}!",
        "km": f"That's about {km:,} kilometers.",
        "outro": OUTRO["overlay"],
    }
    clips, dur = M.say_all(tts, lines)
    fly1 = 2.6
    at = {"q": 0.1}
    at["land"] = max(fly1 + 0.4, at["q"] + dur["q"] + 0.3)
    at["land2"] = at["land"] + dur["land"] + 0.1
    at["km"] = at["land2"] + dur["land2"] + 0.4
    at["outro"] = at["km"] + dur["km"] + 0.7
    end = at["outro"] + dur["outro"] + 1.0
    effects = [(M.sfx_whoosh(), 0.0), (M.sfx_pop(), fly1), (M.sfx_pop(), at["land"] + 0.1),
               (M.sfx_pop(), at["land2"] + 0.1), (M.sfx_ding(), at["km"])]
    wav = out / "audio.wav"
    M.write_audio(wav, end, clips, at, effects)

    region_title = c["region"][:1].upper() + c["region"][1:] if not c["region"].startswith("the ") else c["region"]
    kicker, title, _, _ = header(f"What if {sm} were in {region_title}?")
    f_lab, f_km = M.font(M.SANS_BOLD, 44), M.font(M.SANS_BOLD, 64)
    credit = M.text_layer([M.CREDIT + " · same size on the globe"], M.font(M.SANS, 22), (170, 180, 200, 230), shadow=160)
    pa, pb = view.xy(*p), view.xy(*q)

    def label(d, xy, text, r, above):
        x, y = xy
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill=(255, 255, 255, int(255 * r)), outline=(10, 14, 24, 255), width=3)
        bw = d.textlength(text, font=f_lab) / 2 + 22
        tx = min(W - 20 - bw, max(20 + bw, x))
        ty = y - 52 if above else y + 52
        d.rounded_rectangle([tx - bw, ty - 34, tx + bw, ty + 34], radius=18, fill=(8, 12, 24, int(225 * r)))
        d.text((tx, ty), text, font=f_lab, fill=(255, 255, 255, int(255 * r)), anchor="mm")

    def frame(t):
        u = M.ease(t / fly1)
        hi = M.ease((t - at["land"]) / 0.4)
        img = Image.blend(base, base_hi, 0.75 * hi) if hi > 0 else base.copy()
        M.draw_shape(img, view, geo.moved(m, dst, frac0 + (1 - frac0) * u), M.MOVER, alpha=225)
        img.alpha_composite(kicker, (0, 110))
        img.alpha_composite(title, (0, TITLE_Y))
        d = ImageDraw.Draw(img)
        ra, rb, rk = (M.ease((t - at[k]) / 0.25) for k in ("land", "land2", "km"))
        if rk > 0:
            for k in range(0, 40, 2):
                s0, s1 = k / 40, min(1.0, (k + 1) / 40)
                if s0 > rk:
                    break
                s1 = min(s1, rk)
                d.line([pa[0] + (pb[0] - pa[0]) * s0, pa[1] + (pb[1] - pa[1]) * s0,
                        pa[0] + (pb[0] - pa[0]) * s1, pa[1] + (pb[1] - pa[1]) * s1], fill=(255, 255, 255, 255), width=6)
        if ra > 0:
            label(d, pa, sa, ra, above=True)
        if rb > 0:
            label(d, pb, sbn, rb, above=False)
        if rk > 0:
            M.band(img, 1725, 1835, rk, x0=170, x1=W - 170)
            ImageDraw.Draw(img).text((W / 2, 1780), f"≈ {km:,} km", font=f_km, fill=M.GOLD + (int(255 * rk),), anchor="mm")
        img.alpha_composite(credit, (0, 1862))
        return img

    M.render(out / "video.mp4", wav, end, frame)
    return dict(
        title=f"What if {sm} were in {region_title}? 🌍",
        question=f"What if {sm} were in {region_title}?",
        answer=f"It would stretch from {sa} to {sbn} — about {km:,} km.",
        countries=[m], tags=[sm, c["region"].replace("the ", "")], seconds=end, lines=lines)


RENDER = {"compare": compare, "fit": fit, "overlay": overlay}
