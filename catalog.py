"""お題の候補づくりと、次に出すお題の選び方。

形式は3つ。番号順に compare → fit → overlay → compare … とくり返す。
  compare  どっちが大きい？   地図では同じくらいに見える2国。片方を地球の上で動かして、本当の大きさを見せる
  fit      何個入る？         大きい国に、小さい国が(面積で)いくつ入るか。答えの数だけ形を並べる
  overlay  重ねてみる         細長い国などを別の地域に重ねて、端から端までどこに届くかを見せる(クイズではない)
"""
import math
import random

import geo

FORMATS = ["compare", "fit", "overlay"]

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


CANDIDATES = {"compare": compare_candidates, "fit": fit_candidates, "overlay": overlay_candidates}


def countries_of(c):
    return {c.get(k) for k in ("a", "b", "big", "small", "mover")} - {None}


def choose(fmt, history, seed, top=40, recent=4):
    """まだ出していないお題から、得点の高いものを中心に選ぶ。直近 recent 本の主役の国は避ける。"""
    used = {h["key"] for h in history}
    avoid = set()
    for h in history[-recent:]:
        avoid |= set(h.get("countries", []))
    cands = [c for c in CANDIDATES[fmt]() if c["key"] not in used]
    cands.sort(key=lambda c: -c["score"])
    fresh = [c for c in cands if not countries_of(c) & avoid] or cands
    if not fresh:
        return None
    rng = random.Random(seed)
    pool = fresh[:top]
    weights = [c["score"] for c in pool]
    return rng.choices(pool, weights=weights)[0]
