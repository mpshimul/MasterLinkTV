# clean_m3u.py
import sys
import requests

TIMEOUT = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Range": "bytes=0-1024"
}

def is_stream_alive(url):
    try:
        r = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code in (200, 206):
            return True
    except:
        pass

    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code in (200, 206):
            return True
    except:
        pass

    return False


def clean_m3u(src_url, out_file="playlist.m3u"):
    print("⬇️ Downloading playlist...")
    lines = requests.get(src_url, timeout=30).text.splitlines()

    result = ["#EXTM3U"]
    seen = set()
    extinf = None

    total = kept = dead = dup = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF"):
            extinf = line
            continue

        if line.startswith("#"):
            continue

        if extinf and "://" in line:
            total += 1

            if line in seen:
                dup += 1
                extinf = None
                continue

            print(f"🔍 Checking: {line[:60]}")

            if is_stream_alive(line):
                result.append(extinf)
                result.append(line)
                seen.add(line)
                kept += 1
            else:
                dead += 1

            extinf = None

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(result) + "\n")

    print("\n✅ CLEANING DONE")
    print(f"📺 Total     : {total}")
    print(f"✅ Working   : {kept}")
    print(f"❌ Dead      : {dead}")
    print(f"🧹 Duplicate : {dup}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clean_m3u.py <m3u-url>")
        sys.exit(1)

    clean_m3u(sys.argv[1])