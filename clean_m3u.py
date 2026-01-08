# clean_m3u.py
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----- DOWNLOAD M3U -----
def download(url, filename):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(filename, "wb") as f:
        f.write(r.content)

# ----- STRONG STREAM VALIDATION -----
def is_stream_alive(url):
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

# ----- PROCESS SINGLE ENTRY -----
def process_entry(extinf, url):
    """Return tuple (extinf, url) if alive, else None"""
    if is_stream_alive(url):
        return extinf, url
    return None

# ----- CLEAN M3U -----
def clean_m3u(filename, max_workers=20):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    entries = []
    extinf = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            extinf = line
            continue
        if line.startswith("#"):
            continue
        if extinf and line.startswith("http"):
            entries.append((extinf, line))
            extinf = None

    # Remove duplicates by URL
    unique_entries = []
    seen_urls = set()
    for ext, url in entries:
        if url not in seen_urls:
            unique_entries.append((ext, url))
            seen_urls.add(url)

    result = ["#EXTM3U"]
    kept = skipped = 0

    # ----- PARALLEL VALIDATION -----
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_entry, e, u): (e, u) for e, u in unique_entries}
        for future in as_completed(futures):
            res = future.result()
            if res:
                ext, url = res
                result.append("")
                result.append(ext)
                result.append(url)
                kept += 1
            else:
                skipped += 1

    # ----- WRITE BACK -----
    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result).strip() + '\n')

    print(f"✅ Cleaned {filename}: {kept} streams kept, {skipped} streams removed/dead")

# ----- ENTRY POINT -----
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1].startswith("http"):
        SRC = sys.argv[1]
        OUT = "playlist.m3u"
        try:
            download(SRC, OUT)
            clean_m3u(OUT)
        except Exception as e:
            print(f"Failed: {e}")
            sys.exit(1)
    elif len(sys.argv) == 2:
        clean_m3u(sys.argv[1])
    else:
        print("Usage:")
        print("  python clean_m3u.py <playlist.m3u>")
        print("  python clean_m3u.py <source-url>")
        sys.exit(1)