"""Wait, That Big? のサイト(GitHub Pages、docs/)に、動画の一覧ページと回ごとのページを作る。

データは docs/data/episodes.json(投稿のたびに youtube_upload.py が1件足す)。そこから次を作り直す:
  docs/v/<番号>-<題名>/index.html   回ごとのページ(動画・選択肢・「答えを見る」・面積などの数字)
  docs/v/index.html                全回の一覧(新しい順)
  docs/index.html                  トップの「最新の動画」(<!-- LATEST:START --> 〜 END の間だけ書き換える)
  docs/sitemap.xml                 検索エンジン向けのページ一覧

画像は動画の答えの直前の1コマを縮めた縦長 JPEG(docs/img/<slug>.jpg)。overlay(クイズではない回)は答えの場面。
GitHub Actions の upload ジョブ(外部ライブラリなし)から使うので、標準ライブラリだけで書く。

使い方: python site_gen.py   (docs/data/episodes.json からページを作り直す)
"""
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
DATA = DOCS / "data" / "episodes.json"
SITE = "https://2000re.github.io/wait-that-big"
CHANNEL = "https://www.youtube.com/@wait-that-big"
NAME = "Wait, That Big?"
KIND = {"compare": "Which is bigger?", "fit": "How many fit?", "overlay": "What if…?", "space": "Space: which is wider?"}
ABOUT = ("Flat (Mercator) maps stretch land near the poles. In this video the shape is moved across the globe at its "
         "true size, and areas are calculated on the Earth's surface (WGS84), not on the flat map. "
         'Map data: <a href="https://www.naturalearthdata.com/">Natural Earth</a> (public domain).')
LATEST = 12

e = html.escape


def slugify(text, limit=60):
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:limit].rstrip("-") or "video"


def entry_from(meta, video_id, uploaded_at):
    """make_short.py の meta.json とアップロード結果から、サイト用の1件を作る。"""
    s = meta["site"]
    return {
        "number": meta["number"],
        "slug": f"{meta['number']}-{slugify(s['question'])}",
        "format": meta["format"],
        "video_id": video_id,
        "uploaded_at": uploaded_at,
        **s,
    }


def load():
    return json.loads(DATA.read_text()) if DATA.exists() else []


def save(entries):
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(sorted(entries, key=lambda x: x["number"]), ensure_ascii=False, indent=1) + "\n")


def add(entry, image=None):
    """1件足す(同じ番号があれば置き換える)。image があれば docs/img/<slug>.jpg にコピーする。"""
    if image and Path(image).exists():
        (DOCS / "img").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, DOCS / "img" / f"{entry['slug']}.jpg")
        entry["image"] = f"img/{entry['slug']}.jpg"
    entries = [x for x in load() if x["number"] != entry["number"]]
    entries.append(entry)
    save(entries)


# ---------------------------------------------------------------- 部品


def page(title, description, body, depth, canonical):
    up = "../" * depth
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{e(canonical)}">
<link rel="icon" href="{up}icon.png">
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header><div class="bar">
  <img src="{up}icon.png" alt="">
  <a class="name" href="{up}">{NAME}</a>
  <nav><a href="{up}v/">All videos</a><a href="{up}privacy.html">Privacy</a><a href="{up}terms.html">Terms</a></nav>
</div></header>
<main>
{body}
</main>
<footer><div class="bar">© 2026 {NAME} · <a href="{up}privacy.html">Privacy Policy</a> · <a href="{up}terms.html">Terms of Service</a></div></footer>
</body>
</html>
"""


def card(x, prefix, up):
    img = f'<img src="{up}{e(x["image"])}" alt="" loading="lazy">' if x.get("image") else '<span class="noimg"></span>'
    return f"""<a class="card" href="{prefix}{e(x['slug'])}/">
  {img}
  <span class="card-no">#{x['number']} · {e(KIND.get(x['format'], ''))}</span>
  <span class="card-title">{e(x['question'])}</span>
</a>"""


def episode_page(x, prev, nxt):
    quiz = bool(x.get("choices"))
    title = f"{x['question']} — {NAME} #{x['number']}"
    if quiz:
        desc = (f"True-size map quiz #{x['number']}: {x['question']} "
                f"Choices: {' / '.join(x['choices'])}. Answer inside.")
    else:
        desc = f"True-size map #{x['number']}: {x['question']} {x['result']}"
    details = "".join(f"<li>{e(d)}</li>" for d in x.get("details", []))
    answer = f"""<h2>{e(x['result'])}</h2>
        <ul class="facts">{details}</ul>"""
    if quiz:
        choices = "\n".join(f'    <button type="button" class="choice" data-i="{i}">{e(c)}</button>'
                            for i, c in enumerate(x["choices"]))
        side = f"""<p>Make your guess, then check the answer.</p>
      <div class="choices" data-answer="{x['answer']}">
{choices}
      </div>
      <button type="button" class="reveal">Show the answer</button>
      <div class="answer" hidden>
        {answer}
      </div>"""
        script = """
  <script>
  (function () {
    var box = document.querySelector(".choices"), ans = +box.dataset.answer;
    var panel = document.querySelector(".answer"), btn = document.querySelector(".reveal");
    function reveal(picked) {
      box.querySelectorAll(".choice").forEach(function (b) {
        var i = +b.dataset.i;
        b.disabled = true;
        if (i === ans) b.classList.add("right");
        else if (i === picked) b.classList.add("wrong");
      });
      panel.hidden = false; btn.hidden = true;
    }
    box.addEventListener("click", function (ev) {
      var b = ev.target.closest(".choice"); if (b) reveal(+b.dataset.i);
    });
    btn.addEventListener("click", function () { reveal(-1); });
  })();
  </script>"""
    else:
        side = f"""<div class="answer">
        {answer}
      </div>"""
        script = ""
    nav = []
    if prev:
        nav.append(f'<a href="../{e(prev["slug"])}/">← #{prev["number"]}</a>')
    nav.append('<a href="../">All videos</a>')
    if nxt:
        nav.append(f'<a href="../{e(nxt["slug"])}/">#{nxt["number"]} →</a>')
    body = f"""  <p class="muted">#{x['number']} · {e(KIND.get(x['format'], ''))}</p>
  <h1>{e(x['question'])}</h1>
  <div class="quiz-layout">
    <div class="short">
      <iframe src="https://www.youtube-nocookie.com/embed/{e(x['video_id'])}" title="{NAME} #{x['number']}"
        loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        allowfullscreen></iframe>
    </div>
    <div class="quiz">
      {side}
      <p class="muted credit">{ABOUT}</p>
    </div>
  </div>
  <p class="pager">{' · '.join(nav)}</p>
  <p><a href="{CHANNEL}">New videos on YouTube: @wait-that-big</a></p>{script}"""
    return page(title, desc, body, 2, f"{SITE}/v/{x['slug']}/")


def list_page(entries):
    cards = "\n".join(card(x, "", "../") for x in reversed(entries))
    body = f"""  <h1>All videos</h1>
  <p>Every {NAME} video so far, newest first. Open one to make your guess and see the answer.</p>
  <div class="cards">
{cards}
  </div>"""
    return page(f"All videos — {NAME}",
                f"Every {NAME} video: map quizzes about the real size of countries, "
                "moved across the globe at true scale.", body, 1, f"{SITE}/v/")


def latest_block(entries):
    if not entries:
        return """<!-- LATEST:START (site_gen.py が書き換える) -->
  <h2>Latest videos</h2>
  <p>The first video is coming soon.</p>
  <!-- LATEST:END -->"""
    cards = "\n".join(card(x, "v/", "") for x in list(reversed(entries))[:LATEST])
    return f"""<!-- LATEST:START (site_gen.py が書き換える) -->
  <h2>Latest videos</h2>
  <div class="cards">
{cards}
  </div>
  <p><a href="v/">See all videos →</a></p>
  <!-- LATEST:END -->"""


def sitemap(entries):
    urls = [f"{SITE}/", f"{SITE}/v/"] + [f"{SITE}/v/{x['slug']}/" for x in entries]
    items = "\n".join(f"  <url><loc>{e(u)}</loc></url>" for u in urls)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{items}
</urlset>
"""


def build(docs=DOCS):
    entries = sorted(load(), key=lambda x: x["number"])
    vdir = docs / "v"
    for i, x in enumerate(entries):
        d = vdir / x["slug"]
        d.mkdir(parents=True, exist_ok=True)
        prev = entries[i - 1] if i > 0 else None
        nxt = entries[i + 1] if i + 1 < len(entries) else None
        (d / "index.html").write_text(episode_page(x, prev, nxt))
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "index.html").write_text(list_page(entries))
    top = docs / "index.html"
    s = top.read_text()
    if "LATEST:START" not in s:
        raise SystemExit("docs/index.html に <!-- LATEST:START --> 〜 <!-- LATEST:END --> がありません")
    top.write_text(re.sub(r"<!-- LATEST:START.*?<!-- LATEST:END -->", lambda m: latest_block(entries), s, flags=re.S))
    (docs / "sitemap.xml").write_text(sitemap(entries))
    print(f"site: {len(entries)} videos")


if __name__ == "__main__":
    build()
