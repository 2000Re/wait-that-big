"""地図の計算: 国の形、本当の面積、地球の上での移動、メルカトル図法の画面座標。

地図データ: Natural Earth 1:50m(パブリックドメイン)。面積は WGS84 の楕円体の上で計算する(pyproj)。
"""
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from pyproj import Geod
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from shapely.prepared import prep

DATA = Path(__file__).resolve().parent / "data" / "countries.geojson"
GEOD = Geod(ellps="WGS84")
FEATS = json.loads(DATA.read_text())["features"]
NAMES = {f["properties"]["NAME"] for f in FEATS}
MAIN_BODY_GAP_KM = 500    # 本体の島からこれ以内の島を、同じ「本体」とみなす(遠くの海外領土を除くため)


# ---------------------------------------------------------------- 形と面積


def rings(geom):
    """外周の輪だけ(湖などの穴は省略)。"""
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        yield poly[0]


def unwrap(ring):
    """経度180°をまたぐ輪が、画面を横切る線にならないようにつなぐ。"""
    out, prev = [], None
    for lon, lat in ring:
        if prev is not None:
            while lon - prev > 180:
                lon -= 360
            while lon - prev < -180:
                lon += 360
        out.append((lon, lat))
        prev = lon
    return out


def feature(name):
    for f in FEATS:
        if f["properties"]["NAME"] == name:
            return f
    raise KeyError(name)


def ring_area_km2(ring):
    lons, lats = zip(*ring)
    return abs(GEOD.polygon_area_perimeter(lons, lats)[0]) / 1e6


def _cluster(rs, start, gap_km):
    polys = [Polygon(r) for r in rs]
    keep, todo = {start}, [start]
    gap = gap_km / 111.0          # 度に直したおおよその距離(経度方向は少し甘くなる)
    while todo:
        i = todo.pop()
        for j in range(len(rs)):
            if j not in keep and polys[i].distance(polys[j]) < gap:
                keep.add(j)
                todo.append(j)
    return keep


@lru_cache(maxsize=None)
def body(name):
    """国の「本体」の輪(経度をつないだもの)。いちばん大きい島から、MAIN_BODY_GAP_KM 以内の島を次々にたどって集める。
    遠くの海外領土(フランス領ギアナ、アラスカ、ハワイなど)は入らない。"""
    rs = [unwrap(r) for r in rings(feature(name)["geometry"])]
    big = max(range(len(rs)), key=lambda i: ring_area_km2(rs[i]))
    # 経度180°の反対側にある島(ロシアのチュクチ半島など)は、本島の隣に来るように経度を360°ずらす
    lon_big = sum(lo for lo, _ in rs[big]) / len(rs[big])
    for i, r in enumerate(rs):
        shift = round((lon_big - sum(lo for lo, _ in r) / len(r)) / 360) * 360
        if shift:
            rs[i] = [(lo + shift, la) for lo, la in r]
    keep = _cluster(rs, big, MAIN_BODY_GAP_KM)
    return tuple(tuple(map(tuple, rs[i])) for i in sorted(keep))


@lru_cache(maxsize=None)
def area_km2(name):
    """国全体の面積(km²)。"""
    return sum(ring_area_km2(r) for r in rings(feature(name)["geometry"]))


@lru_cache(maxsize=None)
def body_area_km2(name):
    return sum(ring_area_km2(r) for r in body(name))


def body_share(name):
    """国全体の面積のうち、本体が占める割合。1に近いほど「その形=その国」と言ってよい。"""
    return body_area_km2(name) / area_km2(name)


@lru_cache(maxsize=None)
def compact_body(name, gap_km=150):
    """本体のうち、いちばん大きい島と近く(gap_km 以内でつながる)にまとまっている部分(沖縄などの離れた小島を除く)。"""
    rs = [list(r) for r in body(name)]
    big = max(range(len(rs)), key=lambda i: ring_area_km2(rs[i]))
    return tuple(tuple(rs[i]) for i in sorted(_cluster(rs, big, gap_km)))


def compact_share(name):
    """本体のうち compact_body が占める割合。ノルウェー(スバールバル諸島)のように、離れた大きな島がある国ほど小さい。"""
    return sum(ring_area_km2(r) for r in compact_body(name)) / body_area_km2(name)


def centroid(name):
    """本体の重心(経度・緯度)。いちばん大きい島の重心ではなく、本体全体の面積で重みをつける。"""
    ps = [Polygon(r) for r in body(name)]
    a = sum(p.area for p in ps)
    return (sum(p.centroid.x * p.area for p in ps) / a, sum(p.centroid.y * p.area for p in ps) / a)


def merc_y(lat):
    lat = max(-85.0, min(85.0, lat))
    return math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def inv_merc_y(y):
    return math.degrees(2 * math.atan(math.exp(math.radians(y))) - math.pi / 2)


def merc_area(rs):
    """メルカトル図法の地図の上での見かけの面積(単位は度²。比べるためだけに使う)。"""
    return sum(Polygon([(lo, merc_y(la)) for lo, la in r]).area for r in rs)


# ---------------------------------------------------------------- 地球の上での移動


def to_xyz(lon, lat):
    lo, la = math.radians(lon), math.radians(lat)
    return np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])


def to_lonlat(v):
    return math.degrees(math.atan2(v[1], v[0])), math.degrees(math.asin(max(-1.0, min(1.0, v[2]))))


def _great_circle(src, dst, frac):
    a, b = to_xyz(*src), to_xyz(*dst)
    axis = np.cross(a, b)
    s = np.linalg.norm(axis)
    if s < 1e-12:
        return lambda ring: [tuple(p) for p in ring]
    axis /= s
    ang = math.atan2(s, float(np.dot(a, b))) * frac
    c, sn = math.cos(ang), math.sin(ang)

    def f(ring):
        v = np.array([to_xyz(lo, la) for lo, la in ring])
        v = v * c + np.cross(axis, v) * sn + np.outer(v @ axis, axis) * (1 - c)
        lon = np.degrees(np.arctan2(v[:, 1], v[:, 0]))
        lat = np.degrees(np.arcsin(np.clip(v[:, 2], -1, 1)))
        return list(zip(lon, lat))
    return f


def mover(src, dst, frac=1.0):
    """形を地球の上で src から dst へ frac だけ動かす関数を返す(地球の上での大きさと形は変わらない)。
    北を上に保つため、経度をずらしてから、子午線に沿って緯度を動かす。"""
    dlon = (dst[0] - src[0]) * frac
    mid_lon = src[0] + dlon
    lat_mv = _great_circle((mid_lon, src[1]), (mid_lon, src[1] + (dst[1] - src[1]) * frac), 1.0)

    def f(ring):
        out = lat_mv([(lo + dlon, la) for lo, la in ring])
        return unwrap(out)
    return f


def moved(name, dst, frac=1.0):
    m = mover(centroid(name), dst, frac)
    return [m(r) for r in body(name)]


# ---------------------------------------------------------------- 場所の名前


@lru_cache(maxsize=None)
def _prepared():
    return [(f["properties"]["NAME"], prep(shape(f["geometry"])), shape(f["geometry"])) for f in FEATS
            if f["properties"]["CONTINENT"] != "Antarctica"]


def country_at(lon, lat):
    """(国名, 陸の上か)。海の上なら、いちばん近い国を返す。"""
    lon = (lon + 180) % 360 - 180
    pt = Point(lon, lat)
    best, bd = None, 1e9
    for name, pg, g in _prepared():
        if pg.contains(pt):
            return name, True
    for name, pg, g in _prepared():
        dd = g.distance(pt)
        if dd < bd:
            best, bd = name, dd
    return best, False


def farthest_pair(rs):
    """形の中で、いちばん離れた2点と、その距離(km)。"""
    pts = np.array([p for r in rs for p in r])
    hull = np.array(MultiPolygon([Polygon(r) for r in rs]).convex_hull.exterior.coords) if len(rs) > 1 else \
        np.array(Polygon(rs[0]).convex_hull.exterior.coords)
    del pts
    best = (0.0, None, None)
    for i in range(len(hull)):
        lo, la = np.full(len(hull), hull[i, 0]), np.full(len(hull), hull[i, 1])
        d = GEOD.inv(lo, la, hull[:, 0], hull[:, 1])[2]
        j = int(np.argmax(d))
        if d[j] > best[0]:
            best = (float(d[j]), tuple(hull[i]), tuple(hull[j]))
    return best[1], best[2], best[0] / 1000


# ---------------------------------------------------------------- 画面


class View:
    """メルカトル図法。画面上の (cx, cy) に、経度 lon_c・メルカトル座標 y_c が来るように、1度を k 画素で描く。"""

    def __init__(self, lon_c, y_c, k, cx, cy):
        self.lon_c, self.y_c, self.k, self.cx, self.cy = lon_c, y_c, k, cx, cy

    @classmethod
    def fit(cls, rings_list, box, pad=0.06, max_k=None):
        """rings_list の全部が box(x0, y0, x1, y1)に収まるように。"""
        lons = [lo for rs in rings_list for r in rs for lo, _ in r]
        ys = [merc_y(la) for rs in rings_list for r in rs for _, la in r]
        x0, y0, x1, y1 = box
        lw, yh = max(1e-6, max(lons) - min(lons)), max(1e-6, max(ys) - min(ys))
        k = min((x1 - x0) * (1 - 2 * pad) / lw, (y1 - y0) * (1 - 2 * pad) / yh)
        if max_k:
            k = min(k, max_k)
        return cls((max(lons) + min(lons)) / 2, (max(ys) + min(ys)) / 2, k, (x0 + x1) / 2, (y0 + y1) / 2)

    def xy(self, lon, lat):
        return self.cx + (lon - self.lon_c) * self.k, self.cy - (merc_y(lat) - self.y_c) * self.k

    def lonlat(self, x, y):
        return self.lon_c + (x - self.cx) / self.k, inv_merc_y(self.y_c - (y - self.cy) / self.k)

    def pts(self, ring):
        return [self.xy(lo, la) for lo, la in ring]
