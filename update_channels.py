import sys
import re
import requests
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SETTINGS ---
# Replace with your actual input link
INPUT_URL = "YOUR_INPUT_JS_LINK_HERE" 
OUTPUT_FILE = "ch2.js"
GROUP_ORDER = ["Bangla", "Sports", "Kids", "Hindi", "Movies", "Documentary", "Others"]

def is_stream_alive(url):
    """Check if a specific stream URL is active."""
    headers = {"User-Agent": "VLC/3.0.20", "Range": "bytes=0-4096"}
    try:
        r = requests.get(url, headers=headers, timeout=8, stream=True, verify=False)
        if r.status_code in (200, 206):
            for chunk in r.iter_content(chunk_size=1024):
                if chunk: return True
    except:
        return False
    return False

def parse_complex_js(url):
    """Parses the nested 'sources' JS structure using Regex."""
    print(f"🌐 Fetching: {url}")
    try:
        response = requests.get(url, timeout=15)
        content = response.text
    except Exception as e:
        print(f"❌ Failed to download: {e}")
        return []

    # Regex to capture the entire channel block
    # Looks for name, sources array, img, and category
    channel_blocks = re.findall(r'\{[\s\n]+name: "(.*?)".*?sources: \[(.*?)\].*?img: "(.*?)".*?category: "(.*?)"', content, re.DOTALL)
    
    parsed_channels = []
    for name, sources_text, img, category in channel_blocks:
        # Extract all URLs inside the sources list for this channel
        urls = re.findall(r'url: "(.*?)"', sources_text)
        parsed_channels.append({
            "name": name,
            "urls": urls,
            "logo": img,
            "group": category
        })
    return parsed_channels

def main():
    channels = parse_complex_js(INPUT_URL)
    if not channels:
        print("⚠️ No data found.")
        return

    print(f"⚡ Processing {len(channels)} channels...")
    
    groups = {g: [] for g in GROUP_ORDER}
    
    for ch in channels:
        working_url = None
        # Check each source URL until one works
        for url in ch["urls"]:
            if is_stream_alive(url):
                working_url = url
                break # Found a winner for this channel
        
        if working_url:
            # Map input category to your GROUP_ORDER
            final_group = "Others"
            for g in GROUP_ORDER:
                if g.lower() in ch["group"].lower():
                    final_group = g
                    break
            
            groups[final_group].append({
                "group": final_group,
                "name": ch["name"],
                "stream": working_url,
                "logo": ch["logo"]
            })
            print(f"✅ {ch['name']} [OK]")
        else:
            print(f"❌ {ch['name']} [DEAD]")

    # Write the output file
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"// Generated: {timestamp}\n")
        f.write("window.rawChannels2 = [\n")
        for g in GROUP_ORDER:
            if groups[g]:
                groups[g].sort(key=lambda x: x["name"].lower())
                f.write(f"  // --- {g.upper()} ---\n")
                for item in groups[g]:
                    f.write(f'  {{ group: "{item["group"]}", name: "{item["name"]}", stream: "{item["stream"]}", logo: "{item["logo"]}" }},\n')
        f.write("];\n")
    
    print(f"✨ Done! Created {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
