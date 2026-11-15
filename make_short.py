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
import media as M
import titles

TZ = ZoneInfo("Asia/Tokyo")
HASHTAGS = "#maps #geography #truesize #mapquiz #shorts"
SITE = "https://2000re.github.io/wait-that-big"


def description(info, number):
    return "\n".join([
        info["question"],
        "",
        "Guess before the reveal! 👀",
        "",
        f"Answer: {info['answer']}",
        "",
        "Flat (Mercator) maps stretch land near the poles, so countries far from the equator look much bigger than "
        "they really are. Every shape in this video is moved across the globe at its true size, and areas are "
        "calculated on the Earth's surface (WGS84), not on the flat map.",
        "",
        f"More true-size quizzes: {SITE}/",
        "",
        "Map data: Natural Earth (public domain).",
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
    fmt = K.FORMATS[(number - 1) % len(K.FORMATS)] if args.format == "auto" else args.format
    rng = random.Random(f"{now.date()}:{number}")
    tts = M.make_tts(args.tts)

    tried = []
    for _ in range(6):
        if args.key:
            c = find(args.key)
        else:
            c = K.choose(fmt, history + [{"key": k} for k in tried], f"{now.date()}:{number}:{len(tried)}")
            if c is None:
                raise SystemExit(f"{fmt} の出せるお題がもうありません")
        print("お題:", c["key"])
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
        "description": description(info, number),
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
