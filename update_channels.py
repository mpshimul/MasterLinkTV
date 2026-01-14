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
GROUP_ORDER = ["Bangla", "News", "Sports", "Kids", "Entertainment", "Movie", "Music", "Religious", "Hindi", "Movies", "Documentary", "Others"]
MAX_WORKERS = 8

# Priority domains - streams from these domains will be placed FIRST
PRIORITY_DOMAINS = [
    "gpcdn.net",          # Top priority - fastest
    "cloudfront.net",     # AWS CloudFront - good quality
    "akamaized.net",      # Akamai CDN
    "llnw.tv",            # Limelight
    "cdn77.org",          # CDN77
    "cdn.bitgravity.com", # BitGravity
]

# Good quality but secondary
GOOD_DOMAINS = [
    "wiseplayout.com",
    "amagi.tv",
    "playout.now",
    "now.amagi.tv"
]

def get_domain_priority(url):
    """Get priority score for a URL based on its domain."""
    url_lower = url.lower()
    
    # Priority 1: gpcdn.net and other top CDNs
    for domain in PRIORITY_DOMAINS:
        if domain in url_lower:
            return 1  # Highest priority
    
    # Priority 2: Good quality CDNs
    for domain in GOOD_DOMAINS:
        if domain in url_lower:
            return 2
    
    # Priority 3: Other known reliable domains
    if any(x in url_lower for x in ['.m3u8', '.mpd', 'master.m3u8', 'playlist.m3u8']):
        return 3
    
    # Priority 4: Everything else
    return 4

def sort_sources_by_priority(sources):
    """Sort sources by domain priority."""
    return sorted(sources, key=lambda x: get_domain_priority(x['url']))

def is_stream_alive_advanced(url, source_name=""):
    """Advanced stream checking with special handling for CDNs."""
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://tplay.live",
        "Referer": "https://tplay.live/",
        "Connection": "keep-alive"
    }
    
    # Special headers for priority domains
    if any(domain in url for domain in PRIORITY_DOMAINS):
        headers.update({
            "Accept": "video/webm,video/ogg,video/*;q=0.9,application/ogg;q=0.7,audio/*;q=0.6,*/*;q=0.5",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        })
    
    try:
        # METHOD 1: For priority domains, be more lenient
        if any(domain in url for domain in PRIORITY_DOMAINS):
            # Try quick HEAD request first
            try:
                r = requests.head(
                    url,
                    headers=headers,
                    timeout=5,
                    verify=False,
                    allow_redirects=True
                )
                
                if r.status_code in (200, 206, 302, 301, 307, 308):
                    log_debug(f"✅ {source_name}: Priority domain HEAD {r.status_code}")
                    return True
            except:
                pass
        
        # METHOD 2: Standard GET with small range
        try:
            get_headers = headers.copy()
            get_headers["Range"] = "bytes=0-1024"
            
            r = requests.get(
                url,
                headers=get_headers,
                timeout=8,
                stream=True,
                verify=False,
                allow_redirects=True
            )
            
            if r.status_code in (200, 206):
                chunk = next(r.iter_content(chunk_size=512), None)
                if chunk:
                    # Check for stream signatures
                    if b'#EXTM3U' in chunk or b'MPD' in chunk or b'<?xml' in chunk:
                        log_debug(f"✅ {source_name}: Stream signature found")
                        return True
                    # For priority domains, accept any data
                    if any(domain in url for domain in PRIORITY_DOMAINS):
                        log_debug(f"✅ {source_name}: Priority domain - data received")
                        return True
        except:
            pass
        
        # METHOD 3: For m3u8 files, check content
        if '.m3u8' in url.lower():
            try:
                r = requests.get(
                    url,
                    headers=headers,
                    timeout=10,
                    verify=False,
                    allow_redirects=True
                )
                
                if r.status_code == 200 and '#EXTM3U' in r.text[:100]:
                    log_debug(f"✅ {source_name}: Valid m3u8 manifest")
                    return True
            except:
                pass
        
        log_debug(f"❌ {source_name}: All checks failed")
        return False
        
    except Exception as e:
        log_debug(f"❌ {source_name}: Exception: {type(e).__name__}")
        return False

def log_debug(message):
    """Log debug information."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")

def parse_complex_js(url):
    """Parse the JS file."""
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
        
        # Extract sources
        sources = []
        source_pattern = r'\{[^}]*?name:\s*["\'](.*?)["\'][^}]*?url:\s*["\'](.*?)["\'][^}]*?\}'
        source_matches = re.findall(source_pattern, sources_text, re.DOTALL)
        
        for source_name, source_url in source_matches:
            if source_url.strip():
                source = {
                    "name": source_name.strip() if source_name.strip() else "Source",
                    "url": source_url.strip()
                }
                
                # Detect type
                if '.mpd' in source_url.lower():
                    source["type"] = "dash"
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
    return parsed_channels

def check_channel_sources(channel):
    """Check all sources for a channel and sort by priority."""
    channel_name = channel['name']
    
    # Check which sources are alive
    working_sources = []
    for source in channel['sources']:
        source_name = f"{channel_name} - {source['name']}"
        is_alive = is_stream_alive_advanced(source['url'], source_name)
        
        if is_alive:
            working_sources.append(source)
            log_debug(f"✅ {source_name}")
        else:
            log_debug(f"❌ {source_name}")
    
    # Sort working sources by priority (gpcdn.net first)
    if working_sources:
        working_sources = sort_sources_by_priority(working_sources)
        
        # Rename sources to show priority
        for i, source in enumerate(working_sources):
            priority = get_domain_priority(source['url'])
            
            if priority == 1:
                source['name'] = f"🏆 Fastest (gpcdn.net)"
            elif priority == 2:
                source['name'] = f"⚡ Fast ({source['url'].split('/')[2].split('.')[-2] if '.' in source['url'].split('/')[2] else 'CDN'})"
            else:
                source['name'] = f"Server {i+1}"
        
        log_debug(f"📊 {channel_name}: Sorted {len(working_sources)} sources by priority")
    
    return channel_name, working_sources

def main():
    # Clear debug file
    open(DEBUG_FILE, "w").close()
    
    print("🚀 Starting channel extraction with CDN priority optimization...")
    print("=" * 70)
    print("🏆 Priority order: gpcdn.net > cloudfront.net > other CDNs > other sources")
    print("=" * 70)
    
    # Parse channels
    channels = parse_complex_js(INPUT_URL)
    if not channels:
        print("❌ No channels found")
        sys.exit(1)
    
    # Organize by group
    groups = {g: [] for g in GROUP_ORDER}
    
    # Statistics
    total_priority_sources = 0
    total_sources = 0
    
    # Check channels
    print(f"\n⚡ Checking {len(channels)} channels...")
    
    for idx, ch in enumerate(channels, 1):
        channel_name = ch['name']
        print(f"[{idx:3d}/{len(channels)}] {channel_name[:40]:40s}", end=" ")
        
        channel_name, working_sources = check_channel_sources(ch)
        
        if working_sources:
            # Count priority sources
            priority_count = sum(1 for s in working_sources if get_domain_priority(s['url']) == 1)
            total_priority_sources += priority_count
            total_sources += len(working_sources)
            
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
            
            # Show priority info
            if priority_count > 0:
                print(f"✅ {len(working_sources)} sources ({priority_count} 🏆 priority)")
            else:
                print(f"✅ {len(working_sources)} sources")
        else:
            print(f"❌ 0 sources")
    
    # Write output
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"// Generated: {timestamp}\n")
        f.write("// CDN-PRIORITY version - gpcdn.net streams placed FIRST\n")
        f.write("// Faster loading and better quality support\n")
        f.write("\n")
        f.write("window.rawChannels2 = [\n")
        
        total_channels = 0
        channels_with_priority = 0
        
        for g in GROUP_ORDER:
            if groups[g]:
                group_channels = groups[g]
                total_channels += len(group_channels)
                
                # Count channels with priority sources in this group
                priority_in_group = sum(1 for ch in group_channels 
                                      if any(get_domain_priority(s['url']) == 1 for s in ch['sources']))
                channels_with_priority += priority_in_group
                
                f.write(f"\n    // {'='*50}\n")
                f.write(f"    // {g.upper()} ({len(group_channels)} channels")
                if priority_in_group > 0:
                    f.write(f", {priority_in_group} with 🏆 gpcdn.net")
                f.write(f")\n")
                f.write(f"    // {'='*50}\n\n")
                
                group_channels.sort(key=lambda x: x["name"].lower())
                
                for ch in group_channels:
                    # Mark channels with priority sources
                    has_priority = any(get_domain_priority(s['url']) == 1 for s in ch['sources'])
                    
                    channel_json = json.dumps(ch, indent=4, ensure_ascii=False)
                    f.write("    " + channel_json.replace("\n", "\n    "))
                    f.write(",\n\n")
        
        f.write("];\n")
        
        # Add summary
        f.write(f"\n// SUMMARY - CDN PRIORITY VERSION\n")
        f.write(f"// Total channels: {total_channels}\n")
        f.write(f"// Channels with gpcdn.net: {channels_with_priority}\n")
        f.write(f"// Total sources: {total_sources}\n")
        f.write(f"// Priority (gpcdn.net) sources: {total_priority_sources}\n")
        f.write(f"// Generated with CDN priority optimization\n")
    
    # Print final summary
    print(f"\n{'='*70}")
    print(f"✨ GENERATION COMPLETE - CDN PRIORITY VERSION")
    print(f"{'='*70}")
    print(f"📊 FINAL STATISTICS:")
    print(f"   Total channels: {total_channels}")
    print(f"   Channels with 🏆 gpcdn.net: {channels_with_priority}")
    print(f"   Total sources saved: {total_sources}")
    print(f"   🏆 Priority sources (gpcdn.net): {total_priority_sources}")
    
    if total_channels > 0:
        print(f"   % with gpcdn.net: {(channels_with_priority/total_channels*100):.1f}%")
    
    print(f"   Output file: {OUTPUT_FILE}")
    print(f"{'='*70}")
    
    # Show example of prioritized output
    print(f"\n📝 EXAMPLE OUTPUT STRUCTURE:")
    print(f"   Sources are now sorted with gpcdn.net FIRST:")
    print(f"   [")
    print(f'     {{"name": "🏆 Fastest (gpcdn.net)", "url": "https://gpcdn.net/..."}},')
    print(f'     {{"name": "⚡ Fast (cloudfront)", "url": "https://cloudfront.net/..."}},')
    print(f'     {{"name": "Server 3", "url": "https://other-cdn.com/..."}}')
    print(f"   ]")
    
    # Group summary with priority indicators
    print(f"\n📁 CHANNELS BY CATEGORY (🏆 = has gpcdn.net):")
    for g in GROUP_ORDER:
        if groups[g]:
            channels_in_group = groups[g]
            priority_count = sum(1 for ch in channels_in_group 
                               if any(get_domain_priority(s['url']) == 1 for s in ch['sources']))
            
            if priority_count > 0:
                print(f"   {g:15} : {len(channels_in_group):3d} channels (🏆{priority_count})")
            else:
                print(f"   {g:15} : {len(channels_in_group):3d} channels")

if __name__ == "__main__":
    main()
