"""YouTube の題名を毎回変える。答え(どちらが大きいか・何個か・どこに届くか)は書かない。

形式ごとに型を用意し、その形式が出た回数で順に回す。過去と同じ題名と、同じ形式の前の回と同じ型は飛ばす。
型の名前は upload_history.json の title_style に残り、stats.md で型ごとの再生数を比べられる。
"""
import re

# 形式 → [(型の名前, 題名)]。{a}{b}: 比べる2国、{plural}{big}{small}: 何個入る？、{m}{region}: 重ねてみる
TITLES = {
    "compare": [
        ("classic", "{a} or {b}: which is bigger? 🌍"),
        ("really", "Is {a} really bigger than {b}? 🌍"),
        ("actually", "{a} vs {b}: which is actually bigger? 🌍"),
        ("guess", "Guess which is bigger: {a} or {b}? 🌍"),
        ("lying", "{a} or {b}? Your map might be lying 🌍"),
        ("true_size", "True size: {a} vs {b}. Which is bigger? 🌍"),
        ("surprise", "{a} or {b}? The answer will surprise you 🌍"),
    ],
    "fit": [
        ("classic", "How many {plural} fit in {big}? 🌍"),
        ("guess", "Guess how many {plural} fit inside {big} 🌍"),
        ("vs", "{big} vs {small}: how many fit inside? 🌍"),
        ("can_you", "Can you guess how many {plural} fit in {big}? 🌍"),
        ("fill", "Fill {big} with {plural}: how many does it take? 🌍"),
        ("true_size", "True size: how many {plural} are in {big}? 🌍"),
    ],
    "overlay": [
        ("classic", "What if {m} were in {region}? 🌍"),
        ("drop", "Drop {m} on {region}: where does it reach? 🌍"),
        ("true_size", "{m} moved to {region} at its true size 🌍"),
        ("really", "How big is {m} really? Let's move it to {region} 🌍"),
        ("on_top", "Put {m} on top of {region}. Where does it end? 🌍"),
        ("surprise", "{m} over {region}: the true size will surprise you 🌍"),
    ],
    "space": [
        ("classic", "{body} or {country}: which is wider? 🌍"),
        ("really", "Is {country} really wider than {body}? 🌍"),
        ("vs", "{country} vs {body}: which is bigger across? 🌍"),
        ("cover", "Could {country} cover {body_say}? 🌍"),
        ("guess", "Guess which is wider: {body} or {country}? 🌍"),
        ("true_size", "True size in space: {body} vs {country} 🌍"),
    ],
}


def choose(fmt, vals, history):
    """(題名, 型の名前)。vals: 題名に入れる値。history: upload_history.json の中身。"""
    same = [h for h in history if h.get("format") == fmt]
    last_style = next((h.get("title_style") for h in reversed(same) if h.get("title_style")), None)
    used = {re.sub(r"^\[\d+\]\s*", "", h.get("title", "")) for h in history}
    options = TITLES[fmt]
    for k in range(len(options)):
        name, tpl = options[(len(same) + k) % len(options)]
        style = f"{fmt}_{name}"
        try:
            t = tpl.format(**vals)
        except KeyError:
            continue
        t = t[:1].upper() + t[1:]
        if len(t) <= 92 and t not in used and style != last_style:
            return t, style
    name, tpl = options[0]
    t = tpl.format(**vals)
    return t[:1].upper() + t[1:], f"{fmt}_{name}"
