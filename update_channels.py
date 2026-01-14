import sys
import re
import requests
import urllib3
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Suppress SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SETTINGS ---
INPUT_URL = "https://tplay.live/main.js" 
OUTPUT_FILE = "ch2.js"
DEBUG_FILE = "debug_log.txt"
GROUP_ORDER = ["Bangla", "News", "Sports", "Kids", "Entertainment", "Movie", "Music", "Religious", "Hindi", "Movies", "Documentary", "Others"]
MAX_WORKERS = 10  # Reduce for more reliable checking
TIMEOUT = 10
DEBUG_MODE = True  # Set to True to see what's being skipped

def log_debug(message):
    """Log debug information if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with open(DEBUG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
        print(message)

def is_stream_alive_verbose(url, source_name=""):
    """Check if a stream is alive with verbose debugging."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://tplay.live",
        "Referer": "https://tplay.live/",
        "Connection": "close"
    }
    
    methods_tried = []
    
    try:
        # METHOD 1: Try HEAD first (fastest)
        try:
            start = time.time()
            r = requests.head(
                url, 
                headers=headers, 
                timeout=5, 
                verify=False,
                allow_redirects=True
            )
            elapsed = time.time() - start
            
            methods_tried.append(f"HEAD: {r.status_code} ({elapsed:.2f}s)")
            
            if r.status_code in (200, 206, 302, 301, 307, 308):
                content_type = r.headers.get('Content-Type', '')
                location = r.headers.get('Location', '')
                
                # Check if it looks like a stream
                if 'mpegurl' in content_type or 'video/' in content_type or 'dash' in content_type:
                    log_debug(f"✅ {source_name}: HEAD success - {content_type}")
                    return True
                    
                if location:
                    log_debug(f"✅ {source_name}: HEAD redirect to {location[:50]}...")
                    return True
                    
                if r.status_code == 200:
                    log_debug(f"✅ {source_name}: HEAD 200 OK")
                    return True
        except Exception as e:
            methods_tried.append(f"HEAD failed: {type(e).__name__}")
        
        # METHOD 2: Try GET with small range
        try:
            range_headers = headers.copy()
            range_headers["Range"] = "bytes=0-1024"  # Just 1KB
            
            start = time.time()
            r = requests.get(
                url, 
                headers=range_headers, 
                timeout=6, 
                stream=True, 
                verify=False,
                allow_redirects=True
            )
            elapsed = time.time() - start
            
            methods_tried.append(f"GET(range): {r.status_code} ({elapsed:.2f}s)")
            
            if r.status_code in (200, 206):
                chunk = next(r.iter_content(chunk_size=512), None)
                if chunk:
                    chunk_str = chunk[:100].decode('ascii', errors='ignore')
                    if '#EXTM3U' in chunk_str or 'MPD' in chunk_str:
                        log_debug(f"✅ {source_name}: GET(range) - stream detected")
                        return True
                    else:
                        log_debug(f"⚠️ {source_name}: GET(range) got data but not stream signature: {chunk_str[:50]}")
                        return True  # Still return True if we got data
        except Exception as e:
            methods_tried.append(f"GET(range) failed: {type(e).__name__}")
        
        # METHOD 3: Last resort - try full GET but close quickly
        try:
            start = time.time()
            r = requests.get(
                url, 
                headers=headers, 
                timeout=4, 
                verify=False,
                allow_redirects=True
            )
            elapsed = time.time() - start
            
            methods_tried.append(f"GET: {r.status_code} ({elapsed:.2f}s)")
            
            if r.status_code in (200, 302, 301, 307, 308):
                log_debug(f"✅ {source_name}: GET {r.status_code}")
                return True
        except Exception as e:
            methods_tried.append(f"GET failed: {type(e).__name__}")
        
        # All methods failed
        log_debug(f"❌ {source_name}: All methods failed - {', '.join(methods_tried)}")
        return False
        
    except Exception as e:
        log_debug(f"❌ {source_name}: Exception - {type(e).__name__}")
        return False

def parse_complex_js(url):
    """Parse the JS file with better error handling."""
    print(f"🌐 Fetching: {url}")
    try:
        response = requests.get(url, timeout=20)
        content = response.text
    except Exception as e:
        print(f"❌ Failed to download: {e}")
        return []
    
    # Try multiple patterns to catch all variations
    patterns = [
        # Standard pattern
        r'\{[\s\n]+name:\s*"(.*?)".*?sources:\s*\[(.*?)\].*?img:\s*"(.*?)".*?category:\s*"(.*?)"',
        # Pattern with optional fields
        r'\{[\s\n]+name:\s*"(.*?)".*?sources:\s*\[(.*?)\](?:.*?img:\s*"(.*?)")?(?:.*?category:\s*"(.*?)")?',
        # More flexible pattern
        r'\{[^}]*?name:\s*["\'](.*?)["\'][^}]*?sources:\s*\[(.*?)\][^}]*?img:\s*["\'](.*?)["\'][^}]*?category:\s*["\'](.*?)["\'][^}]*?\}'
    ]
    
    parsed_channels = []
    
    for pattern in patterns:
        channel_blocks = re.findall(pattern, content, re.DOTALL)
        if channel_blocks:
            print(f"📊 Found {len(channel_blocks)} channels with pattern {patterns.index(pattern)+1}")
            break
    
    if not channel_blocks:
        print("⚠️ No channels found with any pattern")
        return []
    
    for name, sources_text, img, category in channel_blocks:
        if not name or not sources_text:
            continue
            
        # Clean up
        name = name.strip()
        img = img.strip() if img else ""
        category = category.strip() if category else ""
        
        # Extract sources
        sources = []
        
        # Try multiple source patterns
        source_patterns = [
            r'\{[^}]*?name:\s*["\'](.*?)["\'][^}]*?url:\s*["\'](.*?)["\'][^}]*?\}',
            r'\{[^}]*?url:\s*["\'](.*?)["\'][^}]*?name:\s*["\'](.*?)["\'][^}]*?\}',
            r'\{.*?name:\s*"(.*?)".*?url:\s*"(.*?)".*?\}'
        ]
        
        for source_pattern in source_patterns:
            source_matches = re.findall(source_pattern, sources_text, re.DOTALL)
            if source_matches:
                break
        
        for match in source_matches:
            if len(match) >= 2:
                source_name = match[0].strip() if match[0].strip() else "Source"
                source_url = match[1].strip() if len(match) > 1 else match[0].strip()
                
                if not source_url:
                    continue
                    
                source = {
                    "name": source_name,
                    "url": source_url
                }
                
                # Auto-detect type
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
    
    print(f"📊 Successfully parsed {len(parsed_channels)} channels")
    return parsed_channels

def main():
    # Clear debug file
    if DEBUG_MODE:
        open(DEBUG_FILE, "w").close()
    
    # Parse channels
    channels = parse_complex_js(INPUT_URL)
    if not channels:
        print("❌ No channels found. Exiting.")
        sys.exit(1)
    
    print(f"\n📊 Starting stream checking for {len(channels)} channels...")
    
    # Organize by group
    groups = {g: [] for g in GROUP_ORDER}
    
    # Statistics
    total_checked = 0
    total_working = 0
    
    for idx, ch in enumerate(channels, 1):
        print(f"\n[{idx:3d}/{len(channels)}] {ch['name'][:40]:40s}", end=" ")
        
        working_sources = []
        
        # Check each source
        for src_idx, source in enumerate(ch['sources'], 1):
            total_checked += 1
            is_alive = is_stream_alive_verbose(source['url'], f"{ch['name']} - {source['name']}")
            
            if is_alive:
                working_sources.append(source)
                total_working += 1
                print(f"✅", end="")
            else:
                print(f"❌", end="")
        
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
            print(f" ➕ {final_group}")
        else:
            print(f" ⚠️ skipped")
    
    # Write output
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"// Generated: {timestamp}\n")
        f.write("// Sources checked with multi-method validation\n")
        f.write(f"// Success rate: {total_working}/{total_checked} ({total_working/total_checked*100:.1f}%)\n")
        f.write("\n")
        f.write("window.rawChannels2 = [\n")
        
        total_channels = 0
        
        for g in GROUP_ORDER:
            if groups[g]:
                total_channels += len(groups[g])
                f.write(f"\n    // {'='*50}\n")
                f.write(f"    // {g.upper()} ({len(groups[g])} channels)\n")
                f.write(f"    // {'='*50}\n\n")
                
                groups[g].sort(key=lambda x: x["name"].lower())
                
                for ch in groups[g]:
                    channel_json = json.dumps(ch, indent=4, ensure_ascii=False)
                    f.write("    " + channel_json.replace("\n", "\n    "))
                    f.write(",\n\n")
        
        f.write("];\n")
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📊 FINAL STATISTICS:")
    print(f"   Sources checked: {total_checked}")
    print(f"   Working sources: {total_working}")
    print(f"   Success rate:    {total_working/total_checked*100:.1f}%")
    print(f"   Channels saved:  {total_channels}")
    print(f"   Output file:     {OUTPUT_FILE}")
    
    if DEBUG_MODE:
        print(f"   Debug log:       {DEBUG_FILE}")
    
    print(f"{'='*60}")
    
    # Group summary
    print("\n📁 CHANNELS BY CATEGORY:")
    for g in GROUP_ORDER:
        if groups[g]:
            print(f"   {g:15} : {len(groups[g]):3d} channels")

if __name__ == "__main__":
    main()
