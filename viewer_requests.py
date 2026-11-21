"""視聴者のリクエスト(コメントで来た「この国を見たい」)を、次の回のお題にする。

requests.json(手で書く)の例:
  [
    {"id": 1, "countries": ["Japan", "Germany"], "format": null, "note": "#12 のコメント", "added": "2026-11-21"},
    {"id": 2, "countries": ["Chile"], "format": "overlay", "note": "", "added": "2026-11-21"}
  ]
  - countries: 国の名前(英語)。"UK"・"Britain"・"Holland" などの言い方でもよい(ALIASES)
  - format: 形式を指定するとき(compare / fit / overlay / space / shape)。null なら、その回の形式で出せれば出す
  - 投稿すると youtube_upload.py が "done"(回の番号)と "video_id" を書き足す。done のあるものは選ばない

選び方(make_short.py): その回の形式で、まだ出していないお題のうち、リクエストの国をすべて含むものがあれば、
いちばん得点の高いものを出す(直近に出た国を避ける決まりは、リクエストには使わない)。読み上げの最初に
「You asked for this one!」、説明の最初に「Requested in the comments」と入れる。
どの形式でも出せない国(国境に争いのある国・地域、遠くに海外領土がある国、小さすぎる国など)は選ばれない。
scan_requests.py が作る requests_candidates.md に、出せるかどうかが出る。
"""
import json
import re
from pathlib import Path

import catalog as K
import geo

ROOT = Path(__file__).resolve().parent
FILE = ROOT / "requests.json"

# コメントでよく使われる別の言い方 → Natural Earth の名前
EXTRA = {
    "britain": "United Kingdom", "great britain": "United Kingdom", "england": "United Kingdom",
    "holland": "Netherlands", "korea": "South Korea", "drc": "Dem. Rep. Congo", "dr congo": "Dem. Rep. Congo",
    "usa": "United States of America", "us": "United States of America", "america": "United States of America",
    "united states": "United States of America", "czech republic": "Czechia", "ivory coast": "Côte d'Ivoire",
}


def aliases():
    """{小文字の言い方: Natural Earth の名前}。主役にできない国(K.C にない国)も、見分けるために入れる。"""
    out = {}
    for n in geo.NAMES:
        out[n.lower()] = n
    for n, (short, spoken, _plural) in K.C.items():
        for s in (n, short, spoken, spoken.replace("the ", "")):
            out[s.lower()] = n
    out.update(EXTRA)
    return out


ALIASES = aliases()


def resolve(name):
    return ALIASES.get(name.strip().lower())


def find_in_text(text):
    """文の中に出てくる国(Natural Earth の名前)を、出てきた順に。"""
    found = []
    low = " " + re.sub(r"[^\w' .-]", " ", text.lower()) + " "
    for alias in sorted(ALIASES, key=len, reverse=True):
        if len(alias) < 3 and alias not in ("uk", "us"):
            continue
        if re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", low):
            n = ALIASES[alias]
            if n not in found:
                found.append(n)
            low = re.sub(rf"(?<![\w]){re.escape(alias)}(?![\w])", " ", low)
    return found


def load():
    try:
        return json.loads(FILE.read_text() or "[]")
    except (OSError, ValueError):
        return []


def save(reqs):
    FILE.write_text(json.dumps(reqs, ensure_ascii=False, indent=2) + "\n")


def candidates(fmt, names, used=()):
    """その形式で、リクエストの国をすべて含む、まだ出していないお題(得点の高い順)。
    2か国の compare・fit は、ふだんの候補(驚きが大きい組み合わせだけ)になくても、その2か国で作る。"""
    out = [c for c in K.CANDIDATES[fmt]() if c["key"] not in used and set(names) <= K.countries_of(c)]
    if not out and len(names) == 2 and fmt in ("compare", "fit") and all(K._ok_size(n) for n in names):
        small, big = sorted(names, key=geo.area_km2)
        r = geo.area_km2(big) / geo.area_km2(small)
        if fmt == "compare" and r >= 1.05:      # ほぼ同じ大きさでも「約1.1倍」と言える
            # 小さい方(a)を大きい方(b)の上へ動かす(episodes.compare は b の方が大きい前提)
            out = [dict(format="compare", key=f"compare:{small}|{big}", a=small, b=big, score=0)]
        elif fmt == "fit" and round(r) >= 2 and K.C[small][2] and geo.compact_share(small) >= 0.9:
            out = [dict(format="fit", key=f"fit:{big}|{small}", big=big, small=small, score=0)]
        out = [c for c in out if c["key"] not in used]
    return sorted(out, key=lambda c: -c["score"])


def formats_for(names, used=()):
    """そのリクエストを出せる形式の一覧。"""
    return [fmt for fmt in K.FORMATS if candidates(fmt, names, used)]


def pick(fmt, history):
    """(お題, リクエスト) か (None, None)。古いリクエストから順に見る。"""
    used = {h["key"] for h in history}
    for req in sorted(load(), key=lambda r: r.get("id", 0)):
        if req.get("done") or (req.get("format") and req["format"] != fmt):
            continue
        names = [resolve(n) for n in req.get("countries", [])]
        if not names or None in names:
            continue
        cands = candidates(fmt, names, used)
        if cands:
            return cands[0], req
    return None, None


def mark_done(req_id, number, video_id):
    reqs = load()
    for r in reqs:
        if r.get("id") == req_id:
            r["done"] = number
            r["video_id"] = video_id
    save(reqs)
