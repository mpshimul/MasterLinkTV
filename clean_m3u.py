# clean_m3u.py
import sys
import requests

def download(url, filename):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(filename, "wb") as f:
        f.write(r.content)

def clean_m3u(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    result = []
    seen_urls = set()
    prev_inf = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTM3U"):
            result = ["#EXTM3U"]
            prev_inf = None
            continue
        if line.startswith("#EXTINF"):
            prev_inf = line
            continue
        if line.startswith("#"):
            continue  # skip #EXTVLCOPT, etc.
        if prev_inf and (line not in seen_urls):
            result.append("")
            result.append(prev_inf)
            result.append(line)
            seen_urls.add(line)
            prev_inf = None

    with open(filename, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result).strip() + '\n')

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
