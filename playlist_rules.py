"""Wait, That Big? の再生リストの決め方(playlists.py が使う)。形式ごとに1つと、通常動画(True Size Challenge)。"""
HISTORIES = ["upload_history.json", "longform_history.json"]

LISTS = {
    "long": ("True Size Challenge: Full Map Quizzes",
             "12-round true-size map quizzes: which country is bigger, and how many fit inside? New episode every week."),
    "compare": ("Which Is Bigger? True Size Country Quiz",
                "Two countries that look the same size on the map. Which one is really bigger?"),
    "fit": ("How Many Fit? True Size Country Quiz",
            "How many of one country fit inside another? Guess, then watch them fill it up."),
    "overlay": ("What If? Countries Moved at Their True Size",
                "Countries dropped onto other regions at their real size, to see how far they reach."),
    "shape": ("Guess the Country by Its Shape",
              "Only the outline: can you name the country?"),
    "space": ("True Size in Space: Planets, Moons and Countries",
              "Countries compared with planets, moons and dwarf planets at the same scale."),
}
LISTS["space_area"] = LISTS["space"]


def for_record(rec):
    if "keys" in rec:                       # longform_history.json(通常動画)
        return [LISTS["long"]]
    fmt = rec.get("format")
    return [LISTS[fmt]] if fmt in LISTS else []
