# m3u_to_js.py
import sys
import re
import json
from datetime import datetime
import requests

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

# ----- STRONG VALIDATION -----
def is_stream_alive(url):
    """Check if stream is alive by reading actual data"""
    headers = {
        "User-Agent": "VLC/3.0.20 LibVLC/3.0.20",
        "Accept": "*/*",
        "Range": "bytes=0-4096",
        "Connection": "close"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10, stream=True)
        if r.status_code not in (200, 206):
            return False
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:
                return True
    except:
        return False
    return False

# ----- DETECT GROUP -----
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

# ----- READ FILE -----
def read_lines(filename):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.readlines()
    except UnicodeDecodeError:
        with open(filename, "r", encoding="latin-1") as f:
            return f.readlines()

# ----- MAIN FUNCTION -----
def parse_m3u_to_js(m3u_file, out_js="ch2.js"):
    groups = {g: [] for g in GROUP_ORDER}
    seen_urls = set()
    seen_names = set()

    lines = read_lines(m3u_file)
    extinf = None

    total = kept = skipped = duplicates = 0

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
            total += 1
            name = extinf.split(",", 1)[1].strip() if "," in extinf else "Unknown"

            # Check for duplicate by name or URL
            if name.lower() in seen_names or line in seen_urls:
                duplicates += 1
                extinf = None
                continue

            def get(attr):
                m = re.search(rf'{attr}="([^"]*)"', extinf)
                return m.group(1) if m else ""

            # Strong validation
            if not is_stream_alive(line):
                skipped += 1
                extinf = None
                continue

            group_title = get("group-title")
            category = detect_group(name, group_title)

            groups[category].append({
                "group": category,
                "name": name,
                "stream": line,
                "logo": get("tvg-logo")
            })

            seen_names.add(name.lower())
            seen_urls.add(line)
            extinf = None
            kept += 1

    # Sort channels A–Z inside each group
    for g in groups:
        groups[g].sort(key=lambda x: x["name"].lower())

    # UTC timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ----- WRITE JS IN RAW FORMAT -----
    with open(out_js, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated IPTV channel list\n")
        f.write(f"// Last updated: {timestamp}\n\n")
        f.write("const rawChannels = [\n")

        for g in GROUP_ORDER:
            if groups[g]:
                f.write(f"  // --- {g.upper()} ---\n")
                for ch in groups[g]:
                    line_js = (
                        f'  {{ group: "{ch["group"]}", '
                        f'name: "{ch["name"]}", '
                        f'stream: "{ch["stream"]}", '
                        f'logo: "{ch["logo"]}" }},\n'
                    )
                    f.write(line_js)
        f.write("];\n")

    print(f"✅ {kept} channels written to {out_js} (skipped {skipped} dead, {duplicates} duplicates)")
    print(f"🕒 Last updated: {timestamp}")

# ----- ENTRY POINT -----
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m3u_to_js.py <playlist.m3u> [output.js]")
        sys.exit(1)

    input_m3u = sys.argv[1]
    output_js = sys.argv[2] if len(sys.argv) > 2 else "ch2.js"

    parse_m3u_to_js(input_m3u, output_js)