"""Natural Earth 1:50m の国境データ(パブリックドメイン)から、使う項目だけを残した data/countries.geojson を作る。

元データ: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_admin_0_countries.geojson
使い方: python tools/prepare_data.py <ダウンロードした ne_50m_admin_0_countries.geojson>
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "countries.geojson"


def rnd(c):
    return [rnd(x) for x in c] if isinstance(c[0], list) else [round(c[0], 3), round(c[1], 3)]


def main(src):
    feats = json.loads(Path(src).read_text())["features"]
    out = [{"type": "Feature", "properties": {k: f["properties"][k] for k in ("NAME", "NAME_LONG", "CONTINENT")},
            "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"])}}
           for f in feats]
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": out}, separators=(",", ":")))
    print(OUT, OUT.stat().st_size // 1024, "KB,", len(out), "countries")


if __name__ == "__main__":
    main(sys.argv[1])
