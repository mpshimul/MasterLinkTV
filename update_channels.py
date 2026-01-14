import sys
import re
import requests
import urllib3
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SETTINGS ---
INPUT_URL = "https://tplay.live/main.js" 
OUTPUT_FILE = "ch2.js"
GROUP_ORDER = ["Bangla", "Sports", "Kids", "Entertainment", "News", "Movie", "Music", "Religious", "Hindi", "Movies", "Documentary", "Others"]
MAX_WORKERS = 15  # Reduce workers for better resource management
TIMEOUT = 5  # Reduce timeout for faster checking

def is_stream_alive(url):
    """Check if a specific stream URL is active (optimized version)."""
    headers = {
        "User-Agent": "VLC/3.0.20 LibVLC/3.0.20",
        "Range": "bytes=0-4096",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "close"
    }
    
    try:
        with requests.Session() as session:
            r = session.get(
                url, 
                headers=headers, 
                timeout=TIMEOUT, 
                stream=True, 
                verify=False,
                allow_redirects=True
            )
            
            if r.status_code in (200, 206):
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: 
                        # Quick check for HLS
                        if b'#EXTM3U' in chunk[:100]:
                            return True
                        # For DASH/MPD
                        if b'MPD' in chunk[:100] or b'<?xml' in chunk[:100]:
                            return True
                        # Any valid data counts
                        return True
                return False
            else:
                return False
                
    except Exception:
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

    # Improved regex to capture the entire channel block
    channel_blocks = re.findall(r'\{[\s\n]+name:\s*"(.*?)".*?sources:\s*\[(.*?)\].*?img:\s*"(.*?)".*?category:\s*"(.*?)"', content, re.DOTALL)
    
    if not channel_blocks:
        print("⚠️ No channels found with new format, trying alternative pattern...")
        # Alternative pattern for different formatting
        channel_blocks = re.findall(r'\{[^}]+name:\s*"(.*?)"[^}]+sources:\s*\[(.*?)\][^}]+img:\s*"(.*?)"[^}]+category:\s*"(.*?)"', content, re.DOTALL)
    
    parsed_channels = []
    for name, sources_text, img, category in channel_blocks:
        # Clean up whitespace
        name = name.strip()
        img = img.strip()
        category = category.strip()
        
        # Extract sources with improved regex
        sources = []
        source_pattern = r'\{[^}]*?name:\s*"(.*?)"[^}]*?url:\s*"(.*?)"(?:[^}]*?type:\s*"(.*?)")?(?:[^}]*?drm:\s*(\{.*?\}))?[^}]*?\}'
        source_matches = re.findall(source_pattern, sources_text, re.DOTALL)
        
        for source_name, source_url, source_type, drm_text in source_matches:
            if not source_url.strip():
                continue  # Skip empty URLs
                
            source = {
                "name": source_name.strip() if source_name.strip() else "Source",
                "url": source_url.strip()
            }
            
            # Auto-detect type
            if '.mpd' in source_url.lower():
                source["type"] = "dash"
            elif '.m3u8' in source_url.lower():
                source["type"] = "hls"
            elif source_type and source_type.strip():
                source["type"] = source_type.strip().lower()
            else:
                source["type"] = "hls"
            
            # Parse DRM if present
            if drm_text and drm_text.strip():
                try:
                    # Simple DRM extraction
                    kid_match = re.search(r'kid:\s*["\'](.*?)["\']', drm_text)
                    key_match = re.search(r'key:\s*["\'](.*?)["\']', drm_text)
                    
                    if kid_match and key_match:
                        source["drm"] = {
                            "kid": kid_match.group(1),
                            "key": key_match.group(1)
                        }
                except:
                    pass
            
            sources.append(source)
        
        if sources:  # Only add if we have sources
            parsed_channels.append({
                "name": name,
                "sources": sources,
                "img": img,
                "category": category
            })
    
    return parsed_channels

def check_source_parallel(source):
    """Check a single source in parallel."""
    is_alive = is_stream_alive(source["url"])
    return source, is_alive

def main():
    channels = parse_complex_js(INPUT_URL)
    if not channels:
        print("⚠️ No channels found.")
        sys.exit(1)
    
    print(f"📊 Found {len(channels)} channels")
    
    # Organize by group
    groups = {g: [] for g in GROUP_ORDER}
    
    # Process channels with progress
    for idx, ch in enumerate(channels, 1):
        print(f"\n[{idx}/{len(channels)}] Checking: {ch['name']}")
        
        working_sources = []
        
        # Check all sources in parallel
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(ch['sources']))) as executor:
            futures = [executor.submit(check_source_parallel, src) for src in ch['sources']]
            
            for future in as_completed(futures):
                source, is_alive = future.result()
                status = "✅" if is_alive else "❌"
                print(f"   {status} {source['name']}")
                if is_alive:
                    working_sources.append(source)
        
        if working_sources:
            # Determine group
            final_group = "Others"
            for g in GROUP_ORDER:
                if g.lower() in ch["category"].lower():
                    final_group = g
                    break
            
            channel_data = {
                "name": ch['name'],
                "sources": working_sources,
                "img": ch['img'],
                "category": final_group,
                "description": f"{final_group} Channel"
            }
            
            groups[final_group].append(channel_data)
            print(f"   ➕ Added to {final_group} category")
        else:
            print(f"   ⚠️ No working sources - skipped")
    
    # Write output file
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"// Generated: {timestamp}\n")
        f.write("// Auto-generated channel list with multiple sources\n")
        f.write("// Format compatible with TVPlay-style player\n")
        f.write("\n")
        f.write("window.rawChannels2 = [\n")
        
        total_channels = 0
        total_sources = 0
        
        for g in GROUP_ORDER:
            if groups[g]:
                channel_count = len(groups[g])
                source_count = sum(len(ch['sources']) for ch in groups[g])
                f.write(f"\n    // {'='*50}\n")
                f.write(f"    // {g.upper()} - {channel_count} channels ({source_count} sources)\n")
                f.write(f"    // {'='*50}\n\n")
                
                groups[g].sort(key=lambda x: x["name"].lower())
                
                for ch in groups[g]:
                    total_channels += 1
                    total_sources += len(ch['sources'])
                    
                    # Format the channel as JSON
                    channel_json = json.dumps(ch, indent=4, ensure_ascii=False)
                    f.write("    " + channel_json.replace("\n", "\n    "))
                    f.write(",\n\n")
        
        f.write("];\n")
        
        # Add summary
        f.write(f"\n// SUMMARY\n")
        f.write(f"// Total channels: {total_channels}\n")
        f.write(f"// Total sources: {total_sources}\n")
        f.write(f"// Avg sources per channel: {total_sources/total_channels:.1f}\n")
        f.write("// Generated by channel-scraper.py\n")
    
    print(f"\n{'='*60}")
    print(f"✨ SUCCESS: Created {OUTPUT_FILE}")
    print(f"📊 Statistics:")
    print(f"   Total channels: {total_channels}")
    print(f"   Total sources: {total_sources}")
    print(f"   Average sources per channel: {total_sources/total_channels:.1f}")
    print(f"{'='*60}")
    
    # Print group summary
    print("\n📁 Channels by category:")
    for g in GROUP_ORDER:
        if groups[g]:
            count = len(groups[g])
            sources = sum(len(ch['sources']) for ch in groups[g])
            print(f"   {g:15} : {count:3d} channels ({sources:3d} sources)")

if __name__ == "__main__":
    main()
