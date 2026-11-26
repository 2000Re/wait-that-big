"""お題の候補づくりと、次に出すお題の選び方。

形式は3つ。番号順に compare → fit → overlay → compare … とくり返す。
  compare  どっちが大きい？   地図では同じくらいに見える2国。片方を地球の上で動かして、本当の大きさを見せる
  fit      何個入る？         大きい国に、小さい国が(面積で)いくつ入るか。答えの数だけ形を並べる
  overlay  重ねてみる         細長い国などを別の地域に重ねて、端から端までどこに届くかを見せる(クイズではない)
  shape    形当て             国のシルエットだけを見せて「どの国？」を3択で当てる。答えで地図の上の本当の位置に収まる
  space    宇宙               月・惑星・衛星の直径と、国の東西の幅を比べる(「月とオーストラリア、幅が広いのは？」)
  space_area 宇宙の面積         天体の表面全体の面積と、国の面積を比べる(「冥王星とロシア、広いのは？」)。
                               CYCLE の space の回で、space と交互に出す(お題は AREA_PAIRS だけ)
"""
import math
from collections import Counter
from functools import lru_cache
import random

import geo

FORMATS = ["compare", "fit", "overlay", "space", "shape", "space_area"]

# 主役にする国: データ上の名前 → (短い名前[題名・ボタン], 読み上げ[冠詞つき], 複数形[何個入る？で使う。不自然なら None])
# 国境に争いのある国・地域(台湾、イスラエル、モロッコ、西サハラ、コソボなど)は主役にしない
C = {
    "Japan": ("Japan", "Japan", "Japans"),
    "United Kingdom": ("UK", "the UK", "UKs"),
    "Germany": ("Germany", "Germany", "Germanys"),
    "France": ("France", "France", "Frances"),            # 本体の割合が低い(海外領土)ので、大きさの回には出ない
    "Italy": ("Italy", "Italy", "Italys"),
    "Spain": ("Spain", "Spain", "Spains"),
    "Portugal": ("Portugal", "Portugal", "Portugals"),
    "Ireland": ("Ireland", "Ireland", "Irelands"),
    "Iceland": ("Iceland", "Iceland", "Icelands"),
    "Norway": ("Norway", "Norway", "Norways"),
    "Sweden": ("Sweden", "Sweden", "Swedens"),
    "Finland": ("Finland", "Finland", "Finlands"),
    "Denmark": ("Denmark", "Denmark", "Denmarks"),
    "Poland": ("Poland", "Poland", "Polands"),
    "Greece": ("Greece", "Greece", "Greeces"),
    "Turkey": ("Turkey", "Turkey", "Turkeys"),
    "Russia": ("Russia", "Russia", None),
    "Canada": ("Canada", "Canada", None),
    "Mexico": ("Mexico", "Mexico", "Mexicos"),
    "Cuba": ("Cuba", "Cuba", "Cubas"),
    "Brazil": ("Brazil", "Brazil", "Brazils"),
    "Argentina": ("Argentina", "Argentina", "Argentinas"),
    "Chile": ("Chile", "Chile", "Chiles"),
    "Peru": ("Peru", "Peru", "Perus"),
    "Colombia": ("Colombia", "Colombia", "Colombias"),
    "Venezuela": ("Venezuela", "Venezuela", "Venezuelas"),
    "Australia": ("Australia", "Australia", "Australias"),
    "New Zealand": ("New Zealand", "New Zealand", "New Zealands"),
    "Indonesia": ("Indonesia", "Indonesia", None),
    "Philippines": ("Philippines", "the Philippines", None),
    "Vietnam": ("Vietnam", "Vietnam", "Vietnams"),
    "Thailand": ("Thailand", "Thailand", "Thailands"),
    "Malaysia": ("Malaysia", "Malaysia", None),
    "South Korea": ("South Korea", "South Korea", "South Koreas"),
    "China": ("China", "China", None),
    "Mongolia": ("Mongolia", "Mongolia", "Mongolias"),
    "India": ("India", "India", "Indias"),
    "Iran": ("Iran", "Iran", "Irans"),
    "Saudi Arabia": ("Saudi Arabia", "Saudi Arabia", None),
    "Egypt": ("Egypt", "Egypt", "Egypts"),
    "Algeria": ("Algeria", "Algeria", None),
    "Nigeria": ("Nigeria", "Nigeria", "Nigerias"),
    "Kenya": ("Kenya", "Kenya", "Kenyas"),
    "Ethiopia": ("Ethiopia", "Ethiopia", "Ethiopias"),
    "South Africa": ("South Africa", "South Africa", None),
    "Madagascar": ("Madagascar", "Madagascar", "Madagascars"),
    "Dem. Rep. Congo": ("DR Congo", "the DR Congo", None),
    "Kazakhstan": ("Kazakhstan", "Kazakhstan", "Kazakhstans"),
    "Greenland": ("Greenland", "Greenland", "Greenlands"),
    "Switzerland": ("Switzerland", "Switzerland", "Switzerlands"),
    "Austria": ("Austria", "Austria", "Austrias"),
    "Netherlands": ("Netherlands", "the Netherlands", None),
    "Sri Lanka": ("Sri Lanka", "Sri Lanka", "Sri Lankas"),
    "Libya": ("Libya", "Libya", None),
    "Bolivia": ("Bolivia", "Bolivia", "Bolivias"),
    "Ecuador": ("Ecuador", "Ecuador", "Ecuadors"),
    "Papua New Guinea": ("Papua New Guinea", "Papua New Guinea", None),
    "Tanzania": ("Tanzania", "Tanzania", "Tanzanias"),
    "Uruguay": ("Uruguay", "Uruguay", "Uruguays"),
    "Romania": ("Romania", "Romania", "Romanias"),
    "Jamaica": ("Jamaica", "Jamaica", "Jamaicas"),
    "Cambodia": ("Cambodia", "Cambodia", "Cambodias"),
    "Nepal": ("Nepal", "Nepal", "Nepals"),
    "Belgium": ("Belgium", "Belgium", "Belgiums"),
}

BODY_SHARE_MIN = 0.97         # 大きさを言う回は、本体(描く形)が国全体のこれ以上の国だけ

OVERLAY_MAX_KM2 = 8e6         # これより大きい国(ロシア、カナダ、中国)は、行き先の地域を覆い尽くすので重ねない

# overlay の行き先: (名前, 読み上げ, 中心の経度・緯度)
REGIONS = [
    ("Europe", "Europe", (12.0, 50.0)),
    ("Africa", "Africa", (20.0, 4.0)),
    ("South America", "South America", (-61.0, -14.0)),
    ("the Middle East", "the Middle East", (45.0, 28.0)),
]


def short(n):
    return C[n][0]


def spoken(n):
    return C[n][1]


def cap(s):
    return s[:1].upper() + s[1:]


def _ok_size(n):
    return n in C and geo.body_share(n) >= BODY_SHARE_MIN


def lat_of(n):
    return geo.centroid(n)[1]


def compare_candidates():
    """(A, B, 得点)。A は地図では大きく見えるが本当は小さい国(極に近い)、B は赤道に近い大きい国。"""
    out = []
    names = [n for n in C if _ok_size(n)]
    for a in names:
        for b in names:
            if a == b or abs(lat_of(a)) < abs(lat_of(b)) + 15:
                continue
            r = geo.area_km2(b) / geo.area_km2(a)
            if not 1.6 <= r <= 40:
                continue
            app = geo.merc_area(geo.body(a)) / geo.merc_area(geo.body(b))
            if app < 0.75:
                continue
            ca, cb = geo.centroid(a), geo.centroid(b)
            if abs(ca[0] - cb[0]) > 150:
                continue
            out.append(dict(format="compare", key=f"compare:{a}|{b}", a=a, b=b, score=min(app, 3) * min(r, 20)))
    return out


def fit_candidates():
    """(B 大きい国, S 小さい国, 得点)。B はまとまった形(いちばん大きな島が本体の大部分)。"""
    out = []
    bigs = [n for n in C if _ok_size(n) and geo.ring_area_km2(max(geo.body(n), key=geo.ring_area_km2))
            >= 0.85 * geo.body_area_km2(n)]
    # 並べる側は、ひとまとまりの形の国だけ(離れた大きな島があると、地図のあちこちに破片が散らばる)
    smalls = [n for n in C if _ok_size(n) and C[n][2] and geo.compact_share(n) >= 0.9]
    for b in bigs:
        for s in smalls:
            if b == s:
                continue
            n = geo.area_km2(b) / geo.area_km2(s)
            if not 3.6 <= n <= 30.4:
                continue
            apparent = geo.merc_area(geo.body(b)) / geo.merc_area(geo.body(s))
            surprise = abs(math.log(n / apparent))
            out.append(dict(format="fit", key=f"fit:{b}|{s}", big=b, small=s, score=1 + 2 * surprise))
    return out


def overlay_candidates():
    """(M 動かす国, 行き先の地域, 得点)。端から端が長い国ほど驚きが大きい。"""
    out = []
    for m in C:
        if geo.body_share(m) < BODY_SHARE_MIN or geo.area_km2(m) > OVERLAY_MAX_KM2 or geo.compact_share(m) < 0.9:
            continue
        _, _, km = geo.farthest_pair(geo.compact_body(m))
        if km < 1300:
            continue
        slim = km / math.sqrt(geo.area_km2(m))        # 細長さ(日本 3.2、チリ 5 など)
        cm = geo.centroid(m)
        for name, say, center in REGIONS:
            if geo.GEOD.inv(cm[0], cm[1], center[0], center[1])[2] / 1000 < 3000:
                continue
            out.append(dict(format="overlay", key=f"overlay:{m}|{name}", mover=m, region=name, region_say=say,
                            center=center, score=km / 1000 * math.sqrt(slim)))
    return out


# 天体: 名前 → (読み上げ, ひとこと, 平均直径 km, 色)。直径は NASA の公表値(Planetary Fact Sheet など)
BODIES = {
    "The Moon": ("the Moon", "Earth's moon", 3474.8, (175, 175, 172)),
    "Mercury": ("Mercury", "the smallest planet", 4879.4, (160, 150, 140)),
    "Mars": ("Mars", "the Red Planet", 6779.0, (205, 115, 75)),
    "Io": ("Io", "a moon of Jupiter", 3643.2, (225, 205, 120)),
    "Europa": ("Europa", "a moon of Jupiter", 3121.6, (215, 205, 185)),
    "Ganymede": ("Ganymede", "Jupiter's largest moon", 5268.2, (165, 155, 145)),
    "Callisto": ("Callisto", "a moon of Jupiter", 4820.6, (125, 115, 105)),
    "Titan": ("Titan", "Saturn's largest moon", 5149.5, (215, 165, 85)),
    "Triton": ("Triton", "Neptune's largest moon", 2706.8, (205, 195, 195)),
    "Pluto": ("Pluto", "a dwarf planet", 2376.6, (205, 175, 145)),
    "Eris": ("Eris", "a dwarf planet", 2326.0, (220, 220, 222)),
    "Charon": ("Charon", "Pluto's largest moon", 1212.0, (150, 150, 156)),
    "Ceres": ("Ceres", "a dwarf planet in the asteroid belt", 939.4, (145, 145, 145)),
    "Titania": ("Titania", "Uranus's largest moon", 1577.8, (172, 167, 162)),
    "Rhea": ("Rhea", "a moon of Saturn", 1527.6, (200, 200, 200)),
    "Vesta": ("Vesta", "a giant asteroid", 525.4, (145, 140, 135)),
    "Enceladus": ("Enceladus", "an icy moon of Saturn", 504.2, (232, 238, 244)),
    "Mimas": ("Mimas", "a moon of Saturn", 396.4, (190, 190, 192)),
}


FAMOUS_BODIES = {"The Moon", "Mars", "Pluto", "Mercury"}

# 宇宙の面積(space_area)のお題。天体の表面積は NASA の平均直径から球として計算(π × 直径²)。
# 国の面積は公式の総面積(陸と内水面。CIA World Factbook の Area: total)。地図データ(Natural Earth)の面積ではなく
# こちらを使う(差が数%しかないので、データの違いで答えが変わらないように)。
# 差が 3% 未満の組み合わせ(エリスとロシア、ケレスとアルゼンチン、ミマスとスペインなど)は、直径の誤差や
# 天体のいびつな形で逆転しかねないので入れない
OFFICIAL_AREA = {"Russia": 17_098_242, "Australia": 7_741_220, "India": 3_287_263, "Brazil": 8_515_770}
AREA_PAIRS = [("Pluto", "Russia"), ("Rhea", "Australia"), ("Titania", "Brazil"), ("Ceres", "India")]
AREA_MIN_GAP = 0.03


def body_surface_km2(b):
    return math.pi * BODIES[b][2] ** 2


def space_area_candidates():
    out = []
    for i, (b, n) in enumerate(AREA_PAIRS):
        r = OFFICIAL_AREA[n] / body_surface_km2(b)
        if abs(r - 1) < AREA_MIN_GAP:
            continue
        out.append(dict(format="space_area", key=f"space_area:{b}|{n}", body=b, country=n,
                        score=(len(AREA_PAIRS) - i) * (2.0 if b in FAMOUS_BODIES else 1.0)))
    return out


@lru_cache(maxsize=None)
def country_width(n):
    """本土(いちばん大きい島)の東西の幅と南北の高さ(km)。正距方位図法で測る。"""
    from pyproj import Proj
    c = geo.centroid(n)
    P = Proj(f"+proj=aeqd +lat_0={c[1]} +lon_0={c[0]} +units=km")
    main = max(geo.body(n), key=geo.ring_area_km2)
    pts = [P(lo, la) for lo, la in main]
    xs, ys = [x for x, _ in pts], [y for _, y in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def space_candidates():
    """(天体, 国, 得点)。天体の直径と国の幅が近いほど(どちらとも言えそうなほど)おもしろい。"""
    out = []
    for b, (_, _, d, _) in BODIES.items():
        for n in C:
            if n == "Greenland" or geo.body_share(n) < 0.9:
                continue
            # 島国(インドネシア、日本など)は、いちばん大きい島の幅が国の幅にならないので使わない
            if geo.ring_area_km2(max(geo.body(n), key=geo.ring_area_km2)) < 0.75 * geo.body_area_km2(n):
                continue
            w, h = country_width(n)
            r = w / d
            if not 0.72 <= r <= 1.4 or abs(r - 1) < 0.05 or h > 1.35 * w:
                continue
            out.append(dict(format="space", key=f"space:{b}|{n}", body=b, country=n,
                            score=(1 / max(0.08, abs(math.log(r)))) * (1.6 if b in FAMOUS_BODIES else 1.0)))
    return out


# 形当て: 形に特徴があって当てがいのある国は、少し多めに出す
ICONIC = {"Italy", "Japan", "Chile", "United Kingdom", "Australia", "India", "Brazil", "Norway", "Greece", "New Zealand",
          "Mexico", "Vietnam", "Madagascar", "South Korea", "Cuba", "Iceland", "Ireland", "Spain", "Turkey",
          "Philippines", "Sri Lanka", "Argentina", "South Africa", "Egypt", "Thailand", "Portugal"}


def continent(n):
    return geo.feature(n)["properties"]["CONTINENT"]


# 形当ては国境線そのものを主役に見せるので、国境に争いのある地域を含む国は出さない(カシミール、クリミアなど)
SHAPE_EXCLUDE = {"India", "China", "Pakistan", "Russia", "Ukraine"}


def shape_candidates():
    out = []
    for n in C:
        if n == "Greenland" or n in SHAPE_EXCLUDE or geo.body_share(n) < 0.9:
            continue
        out.append(dict(format="shape", key=f"shape:{n}", country=n, score=2.0 if n in ICONIC else 1.0))
    return out


def shape_choices(n, rng):
    """(選択肢3つ[短い名前], 正解の位置)。外れは同じ大陸で、面積が1/3〜3倍の国(足りなければ大陸を問わない)。"""
    a = geo.area_km2(n)
    skip = {n, "Greenland"} | SHAPE_EXCLUDE
    pool = [m for m in C if m not in skip and continent(m) == continent(n) and 1 / 3 <= geo.area_km2(m) / a <= 3]
    if len(pool) < 2:
        pool = [m for m in C if m not in skip and 1 / 4 <= geo.area_km2(m) / a <= 4]
    wrong = rng.sample(sorted(pool), 2)
    names = [n] + wrong
    rng.shuffle(names)
    return [short(m) for m in names], names.index(n)


def similar_size(n):
    """別の大陸で、面積がいちばん近い国(0.85〜1.18倍)。なければ None。"""
    a = geo.area_km2(n)
    best = None
    for m in C:
        if m in (n, "Greenland") or continent(m) == continent(n) or geo.body_share(m) < BODY_SHARE_MIN:
            continue
        r = geo.area_km2(m) / a
        if 0.85 <= r <= 1.18 and (best is None or abs(math.log(r)) < best[0]):
            best = (abs(math.log(r)), m)
    return best[1] if best else None


CANDIDATES = {"compare": compare_candidates, "fit": fit_candidates, "overlay": overlay_candidates,
              "space": space_candidates, "shape": shape_candidates, "space_area": space_area_candidates}


def countries_of(c):
    """お題に出てくる国・天体・地域(overlay の行き先)。"""
    return {c.get(k) for k in ("a", "b", "big", "small", "mover", "country", "body", "region")} - {None}


def shown_in(h):
    """投稿記録の1本に出てきた国・天体・地域。countries(overlay では端の2国も)と、key に書かれた名前。"""
    names = set(h.get("countries", []))
    if ":" in h.get("key", ""):
        names |= set(h["key"].split(":", 1)[1].split("|"))
    return names


# 形式の順番(7本周期)。重ねてみる(overlay)と何個入る？(fit)は2回ずつ。2026-11-21 の再生数の平均が
# overlay 2,237・fit 1,839・compare 1,473・space 1,358・shape 1,302 だったので、強い2つの出番を増やした
CYCLE = ["overlay", "fit", "compare", "overlay", "fit", "space", "shape"]
CYCLE_START = 15        # この番号の回から CYCLE を使う(それまでは5つを順番に回していた)


def next_format(history):
    """次の回の形式。番号が CYCLE_START 以降は CYCLE の順。前の回と同じ形式が続くときは1つ先に進める。"""
    number = max([h.get("number", 0) for h in history], default=0) + 1
    if number >= CYCLE_START:
        fmt = CYCLE[(number - CYCLE_START) % len(CYCLE)]
        last = history[-1].get("format") if history else None
        if fmt == last:
            fmt = CYCLE[(number - CYCLE_START + 1) % len(CYCLE)]
        if fmt == "space":
            # 宇宙の回は14本に1本(CYCLE を2周するうちの1回だけ。もう1回は重ねてみる)。2026-11-24 に変更:
            # 宇宙の3本(1日目 1,043〜1,398)が全体の平均 1,902 を3〜4割下回り、平均視聴割合も 80% 前後と一番低かったため
            if (number - CYCLE_START) // len(CYCLE) % 2 == 1:
                return "overlay"
            # 面積比べ(space_area)の残りを先に出す。出し終えたら幅比べ(space)
            used = {h.get("key") for h in history}
            if any(c["key"] not in used for c in space_area_candidates()):
                fmt = "space_area"
        return fmt
    last = next((h.get("format") for h in reversed(history) if h.get("format") in FORMATS), None)
    return FORMATS[(FORMATS.index(last) + 1) % len(FORMATS)] if last else FORMATS[0]


# 視聴者の多い国(2026-11-26 の stats.md: アメリカ 52%・インドネシア 14%・フィリピン 10%・インド 10%)。
# その国(や隣の国)が出る回は、その国の視聴者が集まる(#10 インドネシア → インドネシア 56%、#19 スリランカ → インド 61%)
# ので、出る回の得点を少し上げる。同じ国が続かない決まり(recent・OFTEN_*)はそのまま
AUDIENCE_BOOST = {"Indonesia": 1.6, "Philippines": 1.6, "India": 1.4}

PER_COUNTRY = 2       # 選ぶ候補(上位 top 件)の中で、1つの国が占めてよい数
OFTEN_WINDOW = 20     # この本数のうちに OFTEN_MAX 回出た国は、しばらく出さない
OFTEN_MAX = 2


def choose(fmt, history, seed, top=40, recent=4):
    """まだ出していないお題から、得点の高いものを中心に選ぶ。次の国・天体・地域は避ける
    (比べる相手、overlay の行き先と端の国も含む):
      - 直近 recent 本に出たもの
      - 直近 OFTEN_WINDOW 本に OFTEN_MAX 回以上出たもの(グリーンランドのように、どの組み合わせでも
        得点が高くなる国が出すぎないように。2026-11-20 の時点で、何個入る？の3本ともグリーンランドだった)
    また、候補の上位 top 件の中で、1つの国は PER_COUNTRY 件までにする(上位がその国ばかりにならないように)。"""
    used = {h["key"] for h in history}
    avoid = set()
    for h in history[-recent:]:
        avoid |= shown_in(h)
    seen = Counter(n for h in history[-OFTEN_WINDOW:] for n in shown_in(h))
    regions = {r[0] for r in REGIONS}          # 行き先の地域は4つしかないので、この条件の対象にしない
    avoid |= {n for n, k in seen.items() if k >= OFTEN_MAX and n not in regions}
    cands = [c for c in CANDIDATES[fmt]() if c["key"] not in used]
    for c in cands:                  # 視聴者の多い国が出るお題を少し多めに(AUDIENCE_BOOST)
        boost = max([AUDIENCE_BOOST.get(n, 1.0) for n in countries_of(c)] or [1.0])
        if boost != 1.0:
            c["score"] = c["score"] * boost
    if fmt == "space_area":         # お題が4つしかないので、AREA_PAIRS の順に出す(最初は冥王星とロシア)
        return cands[0] if cands else None
    cands.sort(key=lambda c: -c["score"])
    fresh = [c for c in cands if not countries_of(c) & avoid] or cands
    if not fresh:
        return None
    rng = random.Random(seed)
    pool, per = [], Counter()
    for c in fresh:
        if any(per[n] >= PER_COUNTRY for n in countries_of(c)):
            continue
        pool.append(c)
        per.update(countries_of(c))
        if len(pool) >= top:
            break
    weights = [c["score"] for c in pool]
    return rng.choices(pool, weights=weights)[0]
