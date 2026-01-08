# m3u_to_js.py
import sys
import re
import json
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# ----- STRONG STREAM VALIDATION -----
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

# ----- PROCESS SINGLE CHANNEL -----
def process_channel(extinf, url):
    """Return channel dict if alive, else None"""
    name = extinf.split(",", 1)[1].strip() if "," in extinf else "Unknown"
    if not is_stream_alive(url):
        return None
    def get(attr):
        m = re.search(rf'{attr}="([^"]*)"', extinf)
        return m.group(1) if m else ""
    group_title = get("group-title")
    category = detect_group(name, group_title)
    return {
        "group": category,
        "name": name,
        "stream": url,
        "logo": get("tvg-logo")
    }

# ----- MAIN FUNCTION -----
def parse_m3u_to_js(m3u_file, out_js="ch2.js", max_workers=20):
    lines = read_lines(m3u_file)
    channels_to_check = []

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
            channels_to_check.append((extinf, line))
            extinf = None

    seen_names = set()
    seen_urls = set()
    groups = {g: [] for g in GROUP_ORDER}

    total = len(channels_to_check)
    kept = skipped = duplicates = 0

    # ----- PARALLEL VALIDATION -----
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_channel = {executor.submit(process_channel, e, u): (e, u) for e, u in channels_to_check}
        for future in as_completed(future_to_channel):
            e, u = future_to_channel[future]
            try:
                ch = future.result()
                if not ch:
                    skipped += 1
                    continue
                # Check duplicates by name or URL
                if ch["name"].lower() in seen_names or ch["stream"] in seen_urls:
                    duplicates += 1
                    continue
                groups[ch["group"]].append(ch)
                seen_names.add(ch["name"].lower())
                seen_urls.add(ch["stream"])
                kept += 1
            except Exception:
                skipped += 1

    # Sort channels inside each group
    for g in groups:
        groups[g].sort(key=lambda x: x["name"].lower())

    # UTC timestamp
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ----- WRITE JS -----
    with open(out_js, "w", encoding="utf-8") as f:
        f.write(f"// Auto-generated IPTV channel list\n")
        f.write(f"// Last updated: {timestamp}\n\n")
        f.write("const rawChannels = [\n")
        for g in GROUP_ORDER:
            if groups[g]:
                f.write(f"  // --- {g.upper()} ---\n")
                for ch in groups[g]:
                    f.write(f'  {{ group: "{ch["group"]}", name: "{ch["name"]}", stream: "{ch["stream"]}", logo: "{ch["logo"]}" }},\n')
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