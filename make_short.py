"""次のお題を選んで動画を作り、out/meta.json(題名・説明・タグなど)を書く。

使い方:
  python make_short.py --history upload_history.json --out out                # 本番(Google の声)
  python make_short.py --tts dummy --format fit --out /tmp/x                   # 試し(仮の声・形式を指定)
  python make_short.py --key "overlay:Japan|Europe" --out /tmp/x              # お題を指定
"""
import argparse
import json
import random
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import catalog as K
import episodes as E
import viewer_requests as R
import locales
import media as M
import titles

TZ = ZoneInfo("Asia/Tokyo")
HASHTAGS = "#maps #geography #truesize #mapquiz #shorts"
SITE = "https://2000re.github.io/wait-that-big"


SPACE_NOTE = ("The planet or moon and the country are drawn at the same scale. Diameters are NASA's published mean "
              "diameters; the country's width is measured east to west across its mainland on the Earth's surface "
              "(WGS84). The planet or moon is an illustration, not a photo.")
MAP_NOTES = [
    ("Flat (Mercator) maps stretch land near the poles, so countries far from the equator look much bigger than "
     "they really are. Every shape in this video is moved across the globe at its true size, and areas are "
     "calculated on the Earth's surface (WGS84), not on the flat map."),
    ("Why do the sizes look wrong? Most world maps use the Mercator projection, which stretches everything near the "
     "poles. Here each country is moved across the globe without changing its real size, and every area is measured "
     "on the Earth's surface (WGS84)."),
    ("The world map you grew up with exaggerates countries near the poles. In this video the shapes are shifted over "
     "the globe at their true size, so you can compare them fairly. Areas come from the Earth's surface (WGS84), "
     "not from the flat map."),
]
SPACE_AREA_NOTE = ("The planet or moon and the country are drawn at the same scale. The surface area of the planet or "
                   "moon is calculated from NASA's published mean diameter, treating it as a sphere. The country's area "
                   "is its total area (land and inland water) from the CIA World Factbook. To compare them, the whole "
                   "surface is flattened into a disk with exactly the same area. The planet or moon is an illustration, "
                   "not a photo.")
LEADS = ["Guess before the reveal! 👀", "Make your guess before the answer! 🌍", "Pause and guess first! 🤔",
         "What's your guess? Watch to the end! 👀"]


HERE = Path(__file__).resolve().parent
# 姉妹チャンネル(説明欄の最後で紹介する)
SISTERS = [
    ("🎨 Painted When? — guess the year a famous painting was made", "https://www.youtube.com/@painted-when"),
    ("🛰️ Guess From Space — name famous places from satellite images", "https://www.youtube.com/@guess-from-space"),
    ("🔍 Too Close to Tell — guess the museum object from an extreme close-up", "https://www.youtube.com/@too-close-to-tell"),
]


def latest_long():
    """いちばん新しい通常動画(True Size Challenge)の (番号, URL)。なければ None。"""
    p = HERE / "longform_history.json"
    try:
        hist = json.loads(p.read_text() or "[]")       # 限定公開で上げた回も、あとで公開にしている前提
    except (OSError, ValueError):
        return None
    if not hist:
        return None
    h = max(hist, key=lambda x: x["number"])
    return h["number"], f"https://youtu.be/{h['video_id']}"


TEASER_DAYS = 3        # 通常動画を投稿してからこの日数のうちに、予告編の Short を1本出す


def teaser_plan(history, now=None):
    """(通常動画の番号, URL, お題, 何問目, 問題の数) か None。
    いちばん新しい通常動画を投稿してから TEASER_DAYS 日以内で、まだ予告編を出していなければ、その動画の問題から
    1問(反応のよい「何個入る？」を優先)を選ぶ。その1問は答えまで見せ、最後に「残りは通常動画で」と誘う。"""
    now = now or datetime.now(TZ)
    try:
        hist = json.loads((HERE / "longform_history.json").read_text() or "[]")
    except (OSError, ValueError):
        return None
    hist = [h for h in hist if h.get("video_id")]
    if not hist:
        return None
    lg = max(hist, key=lambda x: x["number"])
    if any(h.get("teaser") == lg["number"] for h in history):
        return None
    if (now - datetime.fromisoformat(lg["uploaded_at"])).total_seconds() > TEASER_DAYS * 86400:
        return None
    keys = lg["keys"]
    order = sorted(range(len(keys)), key=lambda i: (not keys[i].startswith("fit:"), i < 2, i))   # 最初の2問は避ける
    used = {h["key"] for h in history}
    for i in order:
        if keys[i] not in used:
            return lg["number"], f"https://youtu.be/{lg['video_id']}", keys[i], i + 1, len(keys)
    return None


def teaser_overlay(n_long, round_no, total):
    """最後の約2.5秒に重ねる帯「Round 5 of 12 · True Size Challenge #2 / Play all 12 rounds!」。"""
    from PIL import Image, ImageDraw
    l1 = M.text_layer([f"Round {round_no} of {total} · True Size Challenge #{n_long}"], M.font(M.SANS_BOLD, 40),
                      M.WHITE, shadow=230)
    l2 = M.text_layer([f"Play all {total} rounds!"], M.font(M.SANS_BOLD, 64), M.GOLD + (255,), shadow=230)
    y0 = 105                     # 上の問いと選択肢の上に重ねる(下は YouTube のボタンや答えの帯と重なるため)
    hgt = l1.height + l2.height + 40
    band = Image.new("RGBA", (M.W, hgt), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle([40, 0, M.W - 40, hgt], radius=28, fill=(8, 12, 24, 230),
                                           outline=M.GOLD + (220,), width=4)
    band.alpha_composite(l1, (0, 14))
    band.alpha_composite(l2, (0, 14 + l1.height))

    def overlay(img, t, end):
        a = M.ease((t - (end - 2.6)) / 0.4)
        if a > 0:
            img.alpha_composite(M.with_alpha(band, a), (0, y0))
        return img
    return overlay


def promo_lines():
    out = []
    lg = latest_long()
    if lg:
        out += [f"▶️ Try the full 12-round True Size Challenge #{lg[0]}: {lg[1]}", ""]
    out += ["More quizzes from the same creator:"] + [f"{t}: {u}" for t, u in SISTERS] + [""]
    return out


def description(info, number, fmt=None, requested=False, teaser=None):
    return "\n".join([
        *([f"▶️ This is round {teaser[3]} of True Size Challenge #{teaser[0]}. Play all {teaser[4]} rounds: {teaser[1]}",
           ""] if teaser else []),
        *(["🙌 Requested in the comments — thanks for the idea!", ""] if requested else []),
        info["question"],
        "",
        LEADS[number % len(LEADS)],
        "",
        f"Answer: {info['answer']}",
        "",
        SPACE_NOTE if fmt == "space" else SPACE_AREA_NOTE if fmt == "space_area" else MAP_NOTES[number % len(MAP_NOTES)],
        "",
        f"More true-size quizzes: {SITE}/",
        "",
        *promo_lines(),
        "Map data: Natural Earth (public domain)." + (" Sizes: NASA." if fmt == "space" else "")
        + (" Sizes: NASA. Country areas: CIA World Factbook." if fmt == "space_area" else ""),
        "",
        HASHTAGS,
    ])


def tags(info):
    return ["map quiz", "geography", "true size", "mercator projection", "maps", "geography quiz",
            *info["tags"]]


def find(key):
    fmt = key.split(":", 1)[0]
    for c in K.CANDIDATES[fmt]():
        if c["key"] == key:
            return c
    raise SystemExit(f"お題が見つかりません: {key}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default="upload_history.json")
    ap.add_argument("--out", default="out")
    ap.add_argument("--tts", default="google", choices=["google", "dummy"])
    ap.add_argument("--format", default="auto", choices=["auto", *K.FORMATS])
    ap.add_argument("--key", help="お題を指定する(例: 'fit:Australia|Japan')")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    hp = Path(args.history)
    history = json.loads(hp.read_text()) if hp.exists() else []
    number = max([h["number"] for h in history], default=0) + 1
    now = datetime.now(TZ)
    fmt = K.next_format(history) if args.format == "auto" else args.format
    rng = random.Random(f"{now.date()}:{number}")
    tts = M.make_tts(args.tts)

    tried = []
    req = c_req = None
    teaser = teaser_plan(history, now) if not args.key and args.format == "auto" else None
    if teaser:
        # 通常動画の予告編の回(週1本): 通常動画の1問を、いつもの Shorts と同じ形で出し、最後に通常動画へ誘う
        print(f"予告編: True Size Challenge #{teaser[0]} の {teaser[3]}問目 → {teaser[2]}")
        args.key = teaser[2]
        rest = teaser[4] - 1
        M.OVERLAY = teaser_overlay(teaser[0], teaser[3], teaser[4])
    if not args.key and args.format == "auto":
        c_req, req = R.pick(fmt, history)
        if c_req:
            print(f"リクエスト #{req['id']}: {req['countries']} → {c_req['key']}")
    for _ in range(6):
        if args.key:
            c = find(args.key)
        elif req and c_req["key"] not in tried:
            c = c_req
            c["requested"] = True                 # 読み上げに「You asked for this one!」(episodes.vary)
        else:
            req = None
            c = K.choose(fmt, history + [{"key": k} for k in tried], f"{now.date()}:{number}:{len(tried)}")
            if c is None:
                raise SystemExit(f"{fmt} の出せるお題がもうありません")
        print("お題:", c["key"])
        c["number"] = number                      # 言い回しを番号で回す(episodes.vary)
        if teaser:
            c["teaser"] = {"outro": f"That was round {teaser[3]}. Want {rest} more? Tap the link to play the full "
                                    "challenge!"}
        info = E.RENDER[c["format"]](c, tts, out, rng)
        if info:
            break
        print("  このお題は成り立たないので、別のお題にします")
        tried.append(c["key"])
        if teaser:                                # 予告編のお題が作れなければ、ふつうの回にする(投稿は止めない)
            print("  予告編をやめて、ふつうの回にします")
            teaser, args.key, M.OVERLAY = None, None, None
            c.pop("teaser", None)
            continue
        if args.key:
            raise SystemExit("指定のお題は作れませんでした")
    else:
        raise SystemExit("お題を6回選び直しても動画を作れませんでした")

    title, title_style = titles.choose(c["format"], info["title_vals"], history)
    meta = {
        "number": number,
        "key": c["key"],
        "format": c["format"],
        "countries": info["countries"],
        "date": now.date().isoformat(),
        "title": f"[{number}] {title}",
        "title_style": title_style,
        "ending": "short_tail",        # 最後の間を短くした終わり方(2026-11-21〜。stats.md で比べる)
        "description": description(info, number, c["format"], bool(req), teaser),
        "localizations": locales.build(c, number, description(info, number, c["format"], bool(req), teaser)),
        "request_id": req["id"] if req else None,
        "teaser": teaser[0] if teaser else None,     # 予告編の回なら、通常動画の番号(teaser_plan が二度出さないため)
        "tags": tags(info),
        "answer": info["answer"],
        "video": "video.mp4",
        "site_image": "site.jpg",
        "site": info["site"],
        "seconds": round(info["seconds"], 1),
        "narration": info["lines"],
    }
    (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: meta[k] for k in ("number", "key", "title", "seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
