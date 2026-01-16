import sys
import re
import requests
import urllib3
import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SETTINGS ---
INPUT_URL = "https://tplay.live/main.js" 
OUTPUT_FILE = "ch2.js"
DEBUG_FILE = "debug_log.txt"
GROUP_ORDER = ["Bangla", "News", "Sports", "Kids", "Entertainment", "News", "Movie", "Music", "Religious", "Hindi", "Movies", "Documentary", "Others"]
MAX_WORKERS = 8

# Priority domains - streams from these domains will be placed FIRST
PRIORITY_DOMAINS = [
    "gpcdn.net",
    "cloudfront.net",
    "akamaized.net",
    "llnw.tv",
    "cdn77.org",
    "cdn.bitgravity.com",
]

def extract_drm_info(sources_text, source_index):
    """Extract DRM information from sources text for a specific source."""
    try:
        # Find all DRM blocks in the sources text
        drm_pattern = r'drm:\s*\{([^}]+)\}'
        drm_blocks = re.findall(drm_pattern, sources_text, re.DOTALL)
        
        if source_index < len(drm_blocks):
            drm_text = drm_blocks[source_index]
            
            # Extract kid and key
            kid_match = re.search(r'kid:\s*["\']([^"\']+)["\']', drm_text)
            key_match = re.search(r'key:\s*["\']([^"\']+)["\']', drm_text)
            
            if kid_match and key_match:
                return {
                    "kid": kid_match.group(1).strip(),
                    "key": key_match.group(1).strip()
                }
    except:
        pass
    
    return None

def parse_complex_js(url):
    """Parse the JS file with DRM support."""
    print(f"🌐 Fetching: {url}")
    try:
        response = requests.get(url, timeout=30)
        content = response.text
    except Exception as e:
        print(f"❌ Failed to download: {e}")
        return []
    
    # Find all channel blocks
    channel_blocks = re.findall(r'\{[\s\n]+name:\s*"(.*?)".*?sources:\s*\[(.*?)\].*?img:\s*"(.*?)".*?category:\s*"(.*?)"', content, re.DOTALL)
    
    if not channel_blocks:
        print("⚠️ No channels found")
        return []
    
    parsed_channels = []
    
    for name, sources_text, img, category in channel_blocks:
        name = name.strip()
        img = img.strip()
        category = category.strip()
        
        # Extract individual source objects
        # This regex captures each complete source object
        source_objects = re.findall(r'(\{[^}]*?(?:\{[^}]*\}[^}]*)*\})', sources_text)
        
        sources = []
        
        for i, source_obj in enumerate(source_objects):
            # Extract name and url from this source object
            name_match = re.search(r'name:\s*["\']([^"\']+)["\']', source_obj)
            url_match = re.search(r'url:\s*["\']([^"\']+)["\']', source_obj)
            type_match = re.search(r'type:\s*["\']([^"\']+)["\']', source_obj)
            
            if url_match:
                source_url = url_match.group(1).strip()
                source_name = name_match.group(1).strip() if name_match else f"Source {i+1}"
                source_type = type_match.group(1).strip().lower() if type_match else ""
                
                source = {
                    "name": source_name,
                    "url": source_url
                }
                
                # Determine type
                if source_type:
                    source["type"] = source_type
                elif '.mpd' in source_url.lower():
                    source["type"] = "dash"
                elif '.m3u8' in source_url.lower():
                    source["type"] = "hls"
                else:
                    source["type"] = "hls"
                
                # Extract DRM information for this specific source
                drm_info = extract_drm_info(source_obj, 0)  # Check this source object for DRM
                if not drm_info:
                    # Also check the full sources text
                    drm_info = extract_drm_info(sources_text, i)
                
                if drm_info:
                    source["drm"] = drm_info
                    print(f"   🔐 Found DRM for {name}: {source_name}")
                
                sources.append(source)
        
        if not sources:
            # Fallback to simple extraction if above method fails
            simple_sources = re.findall(r'\{[^}]*?name:\s*["\']([^"\']+)["\'][^}]*?url:\s*["\']([^"\']+)["\'][^}]*?\}', sources_text)
            
            for source_name, source_url in simple_sources:
                if source_url.strip():
                    source = {
                        "name": source_name.strip() if source_name.strip() else "Source",
                        "url": source_url.strip()
                    }
                    
                    # Auto-detect type
                    if '.mpd' in source_url.lower():
                        source["type"] = "dash"
                        # Try to find DRM for .mpd files
                        drm_info = extract_drm_info(sources_text, len(sources))
                        if drm_info:
                            source["drm"] = drm_info
                            print(f"   🔐 Found DRM for {name}: {source_name}")
                    elif '.m3u8' in source_url.lower():
                        source["type"] = "hls"
                    else:
                        source["type"] = "hls"
                    
                    sources.append(source)
        
        if sources:
            parsed_channels.append({
                "name": name,
                "sources": sources,
                "img": img,
                "category": category
            })
    
    print(f"📊 Parsed {len(parsed_channels)} channels")
    
    # Count DRM channels
    drm_count = sum(1 for ch in parsed_channels for s in ch['sources'] if 'drm' in s)
    if drm_count > 0:
        print(f"🔐 Found {drm_count} sources with DRM")
    
    return parsed_channels

def get_domain_priority(url):
    """Get priority score for a URL based on its domain."""
    url_lower = url.lower()
    
    # Priority 1: gpcdn.net and other top CDNs
    for domain in PRIORITY_DOMAINS:
        if domain in url_lower:
            return 1
    
    # Priority 2: Everything else
    return 2

def sort_sources_by_priority(sources):
    """Sort sources by domain priority."""
    return sorted(sources, key=lambda x: get_domain_priority(x['url']))

def is_stream_alive_advanced(url, source_name=""):
    """Check if stream is alive, with auto-pass for specific domains."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://tplay.live",
        "Referer": "https://tplay.live/",
    }
    
    # --- ADD THIS BLOCK ---
    # Auto-pass gpcdn.net without checking
    if "gpcdn.net" in url.lower():
        log_debug(f"⚡ {source_name}: Auto-passed (gpcdn.net)")
        return True
    # ----------------------
    
    try:
        # For DASH streams (.mpd), we just need to check if manifest is accessible
        if '.mpd' in url.lower():
            try:
                r = requests.head(url, headers=headers, timeout=8, verify=False, allow_redirects=True)
                if r.status_code in (200, 206, 302, 301):
                    log_debug(f"✅ {source_name}: DASH manifest accessible")
                    return True
            except:
                pass
        
        # For HLS streams
        try:
            r = requests.get(url, headers=headers, timeout=8, stream=True, verify=False, allow_redirects=True)
            if r.status_code in (200, 206):
                chunk = next(r.iter_content(chunk_size=512), None)
                if chunk and b'#EXTM3U' in chunk[:100]:
                    log_debug(f"✅ {source_name}: HLS stream alive")
                    return True
        except:
            pass
        
        log_debug(f"❌ {source_name}: Stream check failed")
        return False
        
    except Exception as e:
        log_debug(f"❌ {source_name}: Exception: {type(e).__name__}")
        return False

def log_debug(message):
    """Log debug information."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def check_channel_sources(channel):
    """Check all sources for a channel."""
    channel_name = channel['name']
    working_sources = []
    
    for source in channel['sources']:
        source_name = f"{channel_name} - {source['name']}"
        is_alive = is_stream_alive_advanced(source['url'], source_name)
        
        if is_alive:
            working_sources.append(source)
    
    # Sort by priority
    if working_sources:
        working_sources = sort_sources_by_priority(working_sources)
    
    return channel_name, working_sources

def main():
    # Clear debug file
    open(DEBUG_FILE, "w").close()
    
    print("🚀 Starting channel extraction with DRM support...")
    print("=" * 70)
    
    # Parse channels
    channels = parse_complex_js(INPUT_URL)
    if not channels:
        print("❌ No channels found")
        sys.exit(1)
    
    # Organize by group
    groups = {g: [] for g in GROUP_ORDER}
    
    # Check channels
    print(f"\n⚡ Checking {len(channels)} channels...")
    
    for idx, ch in enumerate(channels, 1):
        channel_name = ch['name']
        print(f"[{idx:3d}/{len(channels)}] {channel_name[:40]:40s}", end=" ")
        
        channel_name, working_sources = check_channel_sources(ch)
        
        if working_sources:
            # Determine group
            final_group = "Others"
            for g in GROUP_ORDER:
                if g.lower() in ch["category"].lower():
                    final_group = g
                    break
            
            # Add emoji for DRM sources
            for source in working_sources:
                if 'drm' in source:
                    source['name'] = f"🔐 {source['name']}"
                elif get_domain_priority(source['url']) == 1:
                    source['name'] = f"⚡ {source['name']}"
            
            channel_data = {
                "name": ch['name'],
                "sources": working_sources,
                "img": ch['img'],
                "category": final_group,
                "description": f"{final_group} Channel"
            }
            
            groups[final_group].append(channel_data)
            
            # Count DRM sources
            drm_count = sum(1 for s in working_sources if 'drm' in s)
            if drm_count > 0:
                print(f"✅ {len(working_sources)} sources ({drm_count} 🔐)")
            else:
                print(f"✅ {len(working_sources)} sources")
        else:
            print(f"❌ 0 sources")
    
    # Write output
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"// Generated: {timestamp}\n")
        f.write("// Includes DRM support for .mpd streams\n")
        f.write("// Format: {drm: {kid: \"...\", key: \"...\"}}\n")
        f.write("\n")
        f.write("window.rawChannels2 = [\n")
        
        total_channels = 0
        drm_channels = 0
        
        for g in GROUP_ORDER:
            if groups[g]:
                group_channels = groups[g]
                total_channels += len(group_channels)
                
                # Count DRM channels in this group
                drm_in_group = sum(1 for ch in group_channels 
                                  if any('drm' in s for s in ch['sources']))
                drm_channels += drm_in_group
                
                f.write(f"\n    // {'='*50}\n")
                f.write(f"    // {g.upper()} ({len(group_channels)} channels")
                if drm_in_group > 0:
                    f.write(f", {drm_in_group} with 🔐 DRM")
                f.write(f")\n")
                f.write(f"    // {'='*50}\n\n")
                
                group_channels.sort(key=lambda x: x["name"].lower())
                
                for ch in group_channels:
                    channel_json = json.dumps(ch, indent=4, ensure_ascii=False)
                    f.write("    " + channel_json.replace("\n", "\n    "))
                    f.write(",\n\n")
        
        f.write("];\n")
        
        # Add summary
        f.write(f"\n// SUMMARY - WITH DRM SUPPORT\n")
        f.write(f"// Total channels: {total_channels}\n")
        f.write(f"// Channels with DRM: {drm_channels}\n")
        f.write(f"// .mpd streams include drm: {{kid: \"...\", key: \"...\"}}\n")
        f.write(f"// Generated with enhanced DRM parsing\n")
    
    print(f"\n{'='*70}")
    print(f"✨ GENERATION COMPLETE")
    print(f"{'='*70}")
    print(f"📊 FINAL STATISTICS:")
    print(f"   Total channels: {total_channels}")
    print(f"   Channels with 🔐 DRM: {drm_channels}")
    print(f"   Output file: {OUTPUT_FILE}")
    print(f"{'='*70}")
    
    # Show example of DRM output
    print(f"\n📝 EXAMPLE DRM OUTPUT:")
    print(f'   "sources": [')
    print(f'     {{')
    print(f'       "name": "🔐 Auto (DRM)",')
    print(f'       "url": "https://example.com/manifest.mpd",')
    print(f'       "type": "dash",')
    print(f'       "drm": {{')
    print(f'         "kid": "601f58d4b7094d2baf78c85d1d9cb6c9",')
    print(f'         "key": "609e0cc03198455fa36fd2cc3e7f940d"')
    print(f'       }}')
    print(f'     }}')
    print(f'   ]')

if __name__ == "__main__":
    main()
