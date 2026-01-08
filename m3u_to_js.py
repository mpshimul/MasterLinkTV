# m3u_to_js.py
import sys
import re
import json
from datetime import datetime

GROUP_ORDER = [
    "Bangla",
    "Sports",
    "Kids",
    "Hindi",
    "Movies",
    "Documentary",
    "Others"
]

KEYWORDS = {
    "Bangla": [
        "bangla", "bengali", "bd",
        "atn", "btv", "somoy", "jamuna", "dbc",
        "rtv", "ntv", "channel i", "ekattor",
        "maasranga", "boishakhi", "gaan bangla", "duronto"
    ],
    "Sports": [
        "sport", "sports", "cricket", "football", "soccer",
        "sony ten", "ten sports", "star sports",
        "t sports", "gazi tv", "ptv sports",
        "beinsports", "be in sports", "espn",
        "ipl", "bpl", "fifa", "icc", "ucl"
    ],
    "Kids": [
        "kids", "cartoon", "nick", "nickelodeon",
        "disney junior", "disney jr", "hungama",
        "pogo", "toon", "baby tv",
        "cartoon network", "cn"
    ],
    "Hindi": [
        "hindi",
        "zee tv", "zee anmol", "zee cinema",
        "sony tv", "sony sab", "sony pal",
        "star plus", "star bharat",
        "colors", "and tv", "&tv",
        "dangal", "dd national"
    ],
    "Movies": [
        "movie", "movies", "cinema", "films",
        "box office", "bollywood", "hollywood",
        "hbo", "hbo hits", "star movies",
        "sony pix", "flix"
    ],
    "Documentary": [
        "documentary", "docu",
        "discovery", "nat geo", "national geographic",
        "animal planet", "history",
        "science", "wild", "geo wild",
        "investigation"
    ]
}

def detect_group(name, group_title):
    text = f"{name} {group_title}".lower()

    for group in GROUP_ORDER:
        if group not in KEYWORDS:
            continue
        for key in KEYWORDS[group]:
            if len(key) <= 3:
                if re.search(rf"\b{re.escape(key)}\b", text):
                    return group
            else:
                if key in text:
                    return group
    return "Others"


def parse_m3u_to_js(m3u_file, out_js="ch2.js"):
    groups = {g: [] for g in GROUP_ORDER}
    seen = set()

    try:
        lines = open(m3u_file, "r", encoding="utf-8").readlines()
    except UnicodeDecodeError:
        lines = open(m3u_file, "r", encoding="latin-1").readlines()

    extinf = None

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF"):
            extinf = line
            continue

        if line.startswith("#"):
            continue

        if extinf and "://" in line:
            if line in seen:
                extinf = None
                continue

            def get(attr):
                m = re.search(rf'{attr}="([^"]*)"', extinf)
                return m.group(1) if m else ""

            name = extinf.split(",", 1)[1].strip() if "," in extinf else "Unknown"
            group_title = get("group-title")

            category = detect_group(name, group_title)

            groups[category].append({
                "name": name,
                "stream": line,
                "logo": get("tvg-logo"),
                "group": category
            })

            seen.add(line)
            extinf = None

    # Sort A–Z inside each group
    for g in groups:
        groups[g].sort(key=lambda x: x["name"].lower())

    # UTC timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    with open(out_js, "w", encoding="utf-8") as f:
        f.write("// Auto-generated IPTV channel list\n")
        f.write(f"// Last updated: {timestamp}\n\n")
        f.write("const channels = ")
        json.dump(groups, f, indent=2, ensure_ascii=False)
        f.write(";\n")

    total = sum(len(v) for v in groups.values())
    print(f"✅ {total} channels written to {out_js}")
    print(f"🕒 Updated at: {timestamp}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m3u_to_js.py <playlist.m3u> [output.js]")
        sys.exit(1)

    input_m3u = sys.argv[1]
    output_js = sys.argv[2] if len(sys.argv) > 2 else "ch2.js"

    parse_m3u_to_js(input_m3u, output_js)