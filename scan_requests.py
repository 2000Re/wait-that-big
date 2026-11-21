"""最近の動画のコメントから、国の名前を拾って「リクエストの候補」の一覧(requests_candidates.md)を作る。

毎日 .github/workflows/requests.yml から動く。一覧を見て、出したいものを requests.json に書き足すと、
次の回から優先して出る(viewer_requests.py)。自動では requests.json に入れない(荒らしや変な組み合わせを避けるため)。

- コメントは YouTube Data API の commentThreads.list で読む(スコープ youtube.readonly。投稿と同じトークン)
- その動画に出てきた国は数えない(「グリーンランドって小さいんだ」のような感想を、リクエストと取り違えないため)
- 公開のリポジトリに残すので、コメントの本文と書いた人の名前は書かない。国の名前と件数、どの回のコメントかだけ

使い方: python scan_requests.py [--videos 30]
"""
import argparse
import json
import urllib.error
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import catalog as K
import viewer_requests as R
import stats

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "upload_history.json"
OUT = ROOT / "requests_candidates.md"
THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
TZ = ZoneInfo("Asia/Tokyo")


def comments(token, video_id, pages=2):
    """その動画の、上の階層のコメントの本文(返信は含めない)。"""
    out, page = [], None
    for _ in range(pages):
        q = {"part": "snippet", "videoId": video_id, "maxResults": 100, "textFormat": "plainText", "order": "time"}
        if page:
            q["pageToken"] = page
        try:
            res = stats.http(f"{THREADS_URL}?{urllib.parse.urlencode(q)}", headers={"Authorization": f"Bearer {token}"})
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):            # コメントが無効・動画が消えた
                return out
            raise
        for it in res.get("items", []):
            out.append(it["snippet"]["topLevelComment"]["snippet"].get("textDisplay", ""))
        page = res.get("nextPageToken")
        if not page:
            break
    return out


def scan(history, texts_by_number):
    """{国の組(タプル): {"count": 件数, "numbers": 回の番号}}。"""
    found = defaultdict(lambda: {"count": 0, "numbers": set()})
    by_number = {h["number"]: h for h in history}
    for number, texts in texts_by_number.items():
        own = K.shown_in(by_number[number])
        for t in texts:
            names = [n for n in R.find_in_text(t) if n not in own]
            if not names:
                continue
            key = tuple(sorted(names[:3]))
            found[key]["count"] += 1
            found[key]["numbers"].add(number)
    return found


def report(found, now):
    used = set()
    hist = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    used = {h["key"] for h in hist}
    reqs = R.load()
    asked = {tuple(sorted(R.resolve(n) or n for n in r.get("countries", []))) for r in reqs}
    lines = [
        "# リクエストの候補(コメントから)",
        "",
        f"`scan_requests.py` が毎日作り直す(最終更新 {now.astimezone(TZ):%Y-%m-%d %H:%M} JST)。",
        "最近の動画のコメントに出てきた国の名前(その動画に出てきた国は除く)。出したいものを `requests.json` に書き足すと、",
        "次の回から優先して出る。「出せる形式」が空のものは出せない(国境に争いのある国・地域、遠くに海外領土がある国など)。",
        "コメントの本文と書いた人の名前は、ここには残さない。",
        "",
        "| 国 | 件数 | どの回のコメント | 出せる形式 | requests.json |",
        "|---|---:|---|---|---|",
    ]
    rows = sorted(found.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
    for names, v in rows:
        fmts = ", ".join(R.formats_for(list(names), used)) if all(n in K.C for n in names) else ""
        nums = ", ".join(f"#{n}" for n in sorted(v["numbers"]))
        lines.append(f"| {' + '.join(names)} | {v['count']} | {nums} | {fmts} | {'済み' if names in asked else ''} |")
    if not rows:
        lines.append("| (まだなし) | | | | |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--videos", type=int, default=30, help="新しい方から何本の動画のコメントを見るか")
    args = ap.parse_args()
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else []
    recent = [h for h in history if h.get("video_id")][-args.videos:]
    token = stats.access_token()
    texts = {h["number"]: comments(token, h["video_id"]) for h in recent}
    print(f"{len(recent)} 本の動画から {sum(len(v) for v in texts.values())} 件のコメントを読みました")
    found = scan(history, texts)
    OUT.write_text(report(found, datetime.now(timezone.utc)))
    print(f"候補: {len(found)} 件 → {OUT.name}")


if __name__ == "__main__":
    main()
