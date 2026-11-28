"""題名と説明の翻訳(YouTube の localizations)。視聴者の言語が日本語・スペイン語・フランス語・ドイツ語・ポルトガル語なら、
その言語の題名と説明が表示される。AI は使わない: 国名は Natural Earth の NAME_JA など、題名の型と天体・地域の名前は下の表。

フランス語・ドイツ語・ポルトガル語は国名に冠詞や前置詞の変化が付くので、「A ou B : …」のように冠詞の要らない形にしている。
答え(どちらが大きいか・何個か・どこに届くか)は題名に書かない。
"""
import geo

LANGS = ["ja", "es", "fr", "de", "pt"]

TITLES = {
    "compare": {
        "ja": "{a}と{b}、大きいのはどっち？🌍",
        "es": "{a} o {b}: ¿cuál es más grande? 🌍",
        "fr": "{a} ou {b} : quel pays est le plus grand ? 🌍",
        "de": "{a} oder {b}: Welches Land ist größer? 🌍",
        "pt": "{a} ou {b}: qual é maior? 🌍",
    },
    "fit": {
        "ja": "{big}に{small}はいくつ入る？🌍",
        "es": "¿Cuántas veces cabe {small} en {big}? 🌍",
        "fr": "{big} vs {small} : combien de fois ça rentre ? 🌍",
        "de": "{big} vs. {small}: Wie oft passt es hinein? 🌍",
        "pt": "{big} × {small}: quantas vezes cabe? 🌍",
    },
    "overlay": {
        "ja": "{m}を{region}に重ねると？🌍",
        "es": "¿Y si {m} estuviera en {region}? 🌍",
        "fr": "{m} posé sur {region} : jusqu'où ça va ? 🌍",
        "de": "{m} auf {region} gelegt: Wie weit reicht es? 🌍",
        "pt": "{m} sobre {region}: até onde chega? 🌍",
    },
    "shape": {
        "ja": "この形の国はどこ？({continent})🌍",
        "es": "¿Qué país de {continent} tiene esta forma? 🌍",
        "fr": "Quel pays ({continent}) a cette forme ? 🌍",
        "de": "Welches Land ({continent}) hat diese Form? 🌍",
        "pt": "Que país ({continent}) tem esta forma? 🌍",
    },
    "space_area": {
        "ja": "{body}の表面全体と{country}、広いのはどっち？🌍",
        "es": "Toda la superficie de {body} o {country}: ¿cuál es más grande? 🌍",
        "fr": "Toute la surface de {body} ou {country} : lequel est le plus grand ? 🌍",
        "de": "Die ganze Oberfläche von {body} oder {country}: Was ist größer? 🌍",
        "pt": "Toda a superfície de {body} ou {country}: qual é maior? 🌍",
    },
    "space": {
        "ja": "{body}と{country}、幅が広いのはどっち？🌍",
        "es": "{body} o {country}: ¿cuál es más ancho? 🌍",
        "fr": "{body} ou {country} : qui est le plus large ? 🌍",
        "de": "{body} oder {country}: Was ist breiter? 🌍",
        "pt": "{body} ou {country}: qual é mais largo? 🌍",
    },
}

# 説明の1行目(その言語)。そのあとに英語の説明(答え・出典)をそのまま続ける
LEAD = {
    "ja": "答えが出る前に予想してみてね！👀 本当の大きさで比べる地図クイズです。",
    "es": "¡Adivina antes de la respuesta! 👀 Un quiz de mapas con el tamaño real de los países.",
    "fr": "Devine avant la réponse ! 👀 Un quiz de cartes avec la vraie taille des pays.",
    "de": "Rate vor der Auflösung! 👀 Ein Karten-Quiz mit der wahren Größe der Länder.",
    "pt": "Adivinhe antes da resposta! 👀 Um quiz de mapas com o tamanho real dos países.",
}

# overlay の行き先(catalog.REGIONS の名前)。フランス語・ドイツ語・ポルトガル語は、型の前置詞に合う形
REGIONS = {
    "Europe": {"ja": "ヨーロッパ", "es": "Europa", "fr": "l'Europe", "de": "Europa", "pt": "a Europa"},
    "Africa": {"ja": "アフリカ", "es": "África", "fr": "l'Afrique", "de": "Afrika", "pt": "a África"},
    "South America": {"ja": "南アメリカ", "es": "Sudamérica", "fr": "l'Amérique du Sud", "de": "Südamerika",
                      "pt": "a América do Sul"},
    "the Middle East": {"ja": "中東", "es": "Oriente Medio", "fr": "le Moyen-Orient", "de": "den Nahen Osten",
                        "pt": "o Oriente Médio"}
}

# 大陸(Natural Earth の CONTINENT)
CONTINENTS = {
    "Europe": {"ja": "ヨーロッパ", "es": "Europa", "fr": "Europe", "de": "Europa", "pt": "Europa"},
    "Asia": {"ja": "アジア", "es": "Asia", "fr": "Asie", "de": "Asien", "pt": "Ásia"},
    "Africa": {"ja": "アフリカ", "es": "África", "fr": "Afrique", "de": "Afrika", "pt": "África"},
    "North America": {"ja": "北アメリカ", "es": "Norteamérica", "fr": "Amérique du Nord", "de": "Nordamerika",
                      "pt": "América do Norte"},
    "South America": {"ja": "南アメリカ", "es": "Sudamérica", "fr": "Amérique du Sud", "de": "Südamerika",
                      "pt": "América do Sul"},
    "Oceania": {"ja": "オセアニア", "es": "Oceanía", "fr": "Océanie", "de": "Ozeanien", "pt": "Oceania"},
}

# 天体(catalog.BODIES の名前)
BODIES = {
    "The Moon": {"ja": "月", "es": "La Luna", "fr": "Lune", "de": "Mond", "pt": "Lua"},
    "Mercury": {"ja": "水星", "es": "Mercurio", "fr": "Mercure", "de": "Merkur", "pt": "Mercúrio"},
    "Mars": {"ja": "火星", "es": "Marte", "fr": "Mars", "de": "Mars", "pt": "Marte"},
    "Io": {"ja": "イオ", "es": "Ío", "fr": "Io", "de": "Io", "pt": "Io"},
    "Europa": {"ja": "エウロパ", "es": "Europa", "fr": "Europe", "de": "Europa", "pt": "Europa"},
    "Ganymede": {"ja": "ガニメデ", "es": "Ganímedes", "fr": "Ganymède", "de": "Ganymed", "pt": "Ganimedes"},
    "Callisto": {"ja": "カリスト", "es": "Calisto", "fr": "Callisto", "de": "Kallisto", "pt": "Calisto"},
    "Titan": {"ja": "タイタン", "es": "Titán", "fr": "Titan", "de": "Titan", "pt": "Titã"},
    "Triton": {"ja": "トリトン", "es": "Tritón", "fr": "Triton", "de": "Triton", "pt": "Tritão"},
    "Pluto": {"ja": "冥王星", "es": "Plutón", "fr": "Pluton", "de": "Pluto", "pt": "Plutão"},
    "Eris": {"ja": "エリス", "es": "Eris", "fr": "Éris", "de": "Eris", "pt": "Éris"},
    "Charon": {"ja": "カロン", "es": "Caronte", "fr": "Charon", "de": "Charon", "pt": "Caronte"},
    "Ceres": {"ja": "ケレス", "es": "Ceres", "fr": "Cérès", "de": "Ceres", "pt": "Ceres"},
    "Titania": {"ja": "チタニア", "es": "Titania", "fr": "Titania", "de": "Titania", "pt": "Titânia"},
    "Rhea": {"ja": "レア", "es": "Rea", "fr": "Rhéa", "de": "Rhea", "pt": "Reia"},
    "Vesta": {"ja": "ベスタ", "es": "Vesta", "fr": "Vesta", "de": "Vesta", "pt": "Vesta"},
    "Enceladus": {"ja": "エンケラドゥス", "es": "Encélado", "fr": "Encelade", "de": "Enceladus", "pt": "Encélado"},
    "Mimas": {"ja": "ミマス", "es": "Mimas", "fr": "Mimas", "de": "Mimas", "pt": "Mimas"},
}


def country(name, lang):
    p = geo.feature(name)["properties"]
    return p.get(f"NAME_{lang.upper()}") or p.get("NAME_LONG") or name


def build(c, number, description_en):
    """catalog の候補 c から、{言語: {"title", "description"}}。作れない言語は入れない。"""
    fmt = c["format"]
    out = {}
    for lang in LANGS:
        try:
            if fmt == "compare":
                vals = dict(a=country(c["a"], lang), b=country(c["b"], lang))
            elif fmt == "fit":
                vals = dict(big=country(c["big"], lang), small=country(c["small"], lang))
            elif fmt == "overlay":
                vals = dict(m=country(c["mover"], lang), region=REGIONS[c["region"]][lang])
            elif fmt == "shape":
                vals = dict(continent=CONTINENTS[geo.feature(c["country"])["properties"]["CONTINENT"]][lang])
            elif fmt in ("space", "space_area"):
                vals = dict(body=BODIES[c["body"]][lang], country=country(c["country"], lang))
            else:
                continue
            title = f"[{number}] " + TITLES[fmt][lang].format(**vals)
        except KeyError:
            continue
        if len(title) > 100:
            continue
        q = TITLES[fmt][lang].format(**vals)
        out[lang] = {"title": title, "description": f"{q}\n{LEAD[lang]}\n\n{description_en}"[:4900]}
    return out
