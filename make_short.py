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


def promo_lines():
    out = []
    lg = latest_long()
    if lg:
        out += [f"▶️ Try the full 12-round True Size Challenge #{lg[0]}: {lg[1]}", ""]
    out += ["More quizzes from the same creator:"] + [f"{t}: {u}" for t, u in SISTERS] + [""]
    return out


def description(info, number, fmt=None, requested=False):
    return "\n".join([
        *(["🙌 Requested in the comments — thanks for the idea!", ""] if requested else []),
        info["question"],
        "",
        LEADS[number % len(LEADS)],
        "",
        f"Answer: {info['answer']}",
        "",
        SPACE_NOTE if fmt == "space" else MAP_NOTES[number % len(MAP_NOTES)],
        "",
        f"More true-size quizzes: {SITE}/",
        "",
        *promo_lines(),
        "Map data: Natural Earth (public domain)." + (" Sizes: NASA." if fmt == "space" else ""),
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
        info = E.RENDER[c["format"]](c, tts, out, rng)
        if info:
            break
        print("  このお題は成り立たないので、別のお題にします")
        tried.append(c["key"])
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
        "description": description(info, number, c["format"], bool(req)),
        "localizations": locales.build(c, number, description(info, number, c["format"], bool(req))),
        "request_id": req["id"] if req else None,
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
