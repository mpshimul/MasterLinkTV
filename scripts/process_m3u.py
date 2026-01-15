#!/usr/bin/env python3
"""
Process M3U file from GitHub and generate optimized channel list with domain priority
Outputs as JS file with window.rawChannels2 = [
"""

import re
import json
import requests
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

# Configuration
M3U_URL = "https://raw.githubusercontent.com/abusaeeidx/IPTV-Scraper-Zilla/main/BD.m3u"  # Replace with your M3U URL
OUTPUT_FILE = "ch3.js"

# YOUR PRIORITY DOMAINS (in order of preference)
PRIORITY_DOMAINS = [
    "aynascope.net",
    "roarzone.info", 
    "owrcovcrpy.gpcdn.net",
    "gpcdn.net",
]

# Domains that require special headers/tokens (will be excluded)
PROBLEMATIC_DOMAINS = [
    "ott-provider.net",
    "stream-url.com",
    "toffeelive.com",
    "merichunidya.com",
    # Add other domains that require special headers here
]

# Category mapping
CATEGORY_MAPPING = {
    "akash go": "Bangla",
    "bangla": "Bangla",
    "bengali": "Bangla",
    "news": "News",
    "sports": "Sports",
    "kids": "Kids",
    "entertainment": "Entertainment",
    "movie": "Movie",
    "movies": "Movie",
    "music": "Music",
    "hindi": "Hindi",
    "documentary": "Documentary",
    "religious": "Religious",
    "others": "Others",
}

# Default category order for output
GROUP_ORDER = [
    "Bangla",
    "News",
    "Sports",
    "Kids",
    "Entertainment",
    "Movie",
    "Music",
    "Religious",
    "Hindi",
    "Documentary",
    "Others"
]

def get_domain_priority(url):
    """Get priority score for a URL based on your specific domains."""
    url_lower = url.lower()
    
    # Check for problematic domains first
    for domain in PROBLEMATIC_DOMAINS:
        if domain in url_lower:
            return 999  # Will be filtered out
    
    # YOUR PRIORITY ORDER
    for priority, domain in enumerate(PRIORITY_DOMAINS, 1):
        if domain in url_lower:
            return priority
    
    # Non-priority HTTPS URLs
    if url.startswith('https://'):
        return 100
    
    # Non-priority HTTP URLs
    if url.startswith('http://'):
        return 101
    
    return 102

def extract_domain(url):
    """Extract clean domain from URL for naming."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Remove common prefixes
        for prefix in ['www.', 'edge.', 'cdn.', 'stream.', 'live.', 'tv.', 'video.', 
                      'tvsen', 'edge2.', 'owrcovcrpy.']:
            if domain.lower().startswith(prefix.lower()):
                domain = domain[len(prefix):]
        
        # Extract main domain parts
        parts = domain.split('.')
        if len(parts) >= 2:
            if 'aynascope.net' in domain.lower():
                return "aynascope.net"
            elif 'roarzone.info' in domain.lower():
                return "roarzone.info"
            elif 'gpcdn.net' in domain.lower():
                return "gpcdn.net"
            return f"{parts[-2]}.{parts[-1]}"
        
        return domain
    except:
        return "unknown"

def has_problematic_pattern(url):
    """Check if URL has patterns that indicate header requirements."""
    url_lower = url.lower()
    
    # Check for problematic domains
    for domain in PROBLEMATIC_DOMAINS:
        if domain in url_lower:
            return True
    
    # Check for very long tokens/keys in URL
    if '?' in url:
        query = url.split('?')[1]
        for param in query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if len(value) > 100:
                    return True
    
    return False

def parse_m3u_file(content):
    """Parse M3U content and extract channels with multiple sources."""
    channels = []
    
    lines = content.strip().split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF:'):
            extinf_data = line[8:]
            
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf_data)
            group_match = re.search(r'group-title="([^"]*)"', extinf_data)
            
            # Extract channel name
            comma_pos = extinf_data.rfind(',')
            if comma_pos != -1:
                channel_name = extinf_data[comma_pos + 1:].strip()
            else:
                name_match = re.search(r'tvg-name="([^"]*)"', extinf_data)
                channel_name = name_match.group(1) if name_match else "Unknown"
            
            # Get category
            if group_match:
                raw_group = group_match.group(1).strip().lower()
                category = None
                for key, value in CATEGORY_MAPPING.items():
                    if key in raw_group:
                        category = value
                        break
                if not category:
                    category = raw_group.title()
            else:
                category = "Others"
            
            # Clean channel name
            channel_name = ' '.join(channel_name.split())
            logo_url = logo_match.group(1) if logo_match else ""
            
            # Find URL
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            
            if j < len(lines):
                url = lines[j].strip()
                if url and not url.startswith('#'):
                    # Skip problematic URLs
                    if has_problematic_pattern(url):
                        i = j + 1
                        continue
                    
                    domain = extract_domain(url)
                    
                    # Auto-detect stream type
                    if '.mpd' in url.lower():
                        stream_type = "dash"
                    elif '.m3u8' in url.lower() or 'm3u8?' in url.lower():
                        stream_type = "hls"
                    elif url.endswith('.m3u'):
                        stream_type = "hls"
                    else:
                        stream_type = "hls"
                    
                    source = {
                        "name": domain,
                        "url": url,
                        "type": stream_type
                    }
                    
                    channel = {
                        "name": channel_name,
                        "category": category,
                        "img": logo_url,  # Using 'img' to match your original format
                        "sources": [source]
                    }
                    
                    channels.append(channel)
            
            i = j + 1
        else:
            i += 1
    
    return channels

def merge_channel_sources(channels):
    """Merge multiple entries of the same channel into a single entry."""
    merged_channels = {}
    
    for channel in channels:
        channel_name = channel["name"].lower().strip()
        
        if channel_name not in merged_channels:
            merged_channels[channel_name] = {
                "name": channel["name"],
                "category": channel["category"],
                "img": channel["img"],
                "sources": []
            }
        
        # Add all sources
        for source in channel["sources"]:
            existing_urls = [s["url"] for s in merged_channels[channel_name]["sources"]]
            if source["url"] not in existing_urls:
                merged_channels[channel_name]["sources"].append(source)
        
        # Update logo if needed
        if not merged_channels[channel_name]["img"] and channel["img"]:
            merged_channels[channel_name]["img"] = channel["img"]
    
    return list(merged_channels.values())

def prioritize_and_filter_sources(channels):
    """Prioritize sources and filter out problematic ones."""
    filtered_channels = []
    
    for channel in channels:
        valid_sources = []
        for source in channel["sources"]:
            if not has_problematic_pattern(source["url"]):
                valid_sources.append(source)
        
        if not valid_sources:
            continue
        
        # Sort by priority
        valid_sources.sort(key=lambda x: get_domain_priority(x["url"]))
        
        # Rename with emojis
        for source in valid_sources:
            priority = get_domain_priority(source["url"])
            domain = source["name"]
            
            # Top 3 domains get gold star
            if any(priority_domain in source["url"].lower() 
                  for priority_domain in PRIORITY_DOMAINS[:3]):
                source["name"] = f"⭐ {domain}"
            elif priority <= 3:
                source["name"] = f"⚡ {domain}"
            elif priority == 100:
                source["name"] = f"🔗 {domain}"
            elif priority == 101:
                source["name"] = f"🌐 {domain}"
            else:
                source["name"] = f"📡 {domain}"
        
        channel["sources"] = valid_sources
        filtered_channels.append(channel)
    
    return filtered_channels

def categorize_channels(channels):
    """Organize channels by standardized category."""
    categorized = defaultdict(list)
    
    for channel in channels:
        category = channel["category"]
        
        category_lower = category.lower()
        standardized_category = None
        
        for key, value in CATEGORY_MAPPING.items():
            if key in category_lower:
                standardized_category = value
                break
        
        if not standardized_category:
            for group in GROUP_ORDER:
                if group.lower() in category_lower:
                    standardized_category = group
                    break
        
        if not standardized_category:
            standardized_category = "Others"
        
        categorized[standardized_category].append(channel)
    
    return categorized

def generate_js_output(categorized_channels):
    """Generate JS file output starting with window.rawChannels2 = [."""
    
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    js_content = []
    js_content.append(f"// Generated: {timestamp}")
    js_content.append(f"// Priority domains: {', '.join(PRIORITY_DOMAINS)}")
    js_content.append("// Format optimized for tplay.live")
    js_content.append("")
    js_content.append("window.rawChannels2 = [")
    js_content.append("")
    
    total_channels = 0
    
    # Process categories in order
    for category in GROUP_ORDER:
        if category in categorized_channels and categorized_channels[category]:
            channels = categorized_channels[category]
            total_channels += len(channels)
            
            # Add category header
            js_content.append(f"    // {'='*50}")
            js_content.append(f"    // {category.upper()} ({len(channels)} channels)")
            js_content.append(f"    // {'='*50}")
            js_content.append("")
            
            # Sort channels alphabetically
            channels.sort(key=lambda x: x["name"].lower())
            
            for channel in channels:
                # Convert to JSON and indent properly
                channel_json = json.dumps(channel, indent=4, ensure_ascii=False)
                
                # Add indentation for JS array
                indented_json = "    " + channel_json.replace("\n", "\n    ")
                js_content.append(indented_json)
                js_content.append("    ,")
                js_content.append("")
    
    # Remove trailing comma from last entry
    if js_content[-2].strip() == ",":
        js_content[-2] = js_content[-2].rstrip(",")
    
    js_content.append("];")
    js_content.append("")
    
    # Add statistics
    stats = calculate_statistics(categorized_channels)
    js_content.append(f"// STATISTICS")
    js_content.append(f"// Total channels: {stats['total_channels']}")
    js_content.append(f"// Total sources: {stats['total_sources']}")
    js_content.append(f"// Top priority sources (⭐): {stats['top_priority_sources']}")
    js_content.append(f"// Other priority sources (⚡): {stats['priority_sources']}")
    js_content.append(f"// Regular sources: {stats['regular_sources']}")
    js_content.append(f"// Categories: {stats['categories']}")
    js_content.append(f"// Generated with M3U processor")
    
    return "\n".join(js_content)

def calculate_statistics(categorized_channels):
    """Calculate statistics from categorized channels."""
    total_channels = 0
    total_sources = 0
    top_priority = 0
    priority = 0
    regular = 0
    
    for category, channels in categorized_channels.items():
        total_channels += len(channels)
        for channel in channels:
            total_sources += len(channel["sources"])
            for source in channel["sources"]:
                url = source["url"].lower()
                if any(domain in url for domain in PRIORITY_DOMAINS[:3]):
                    top_priority += 1
                elif any(domain in url for domain in PRIORITY_DOMAINS[3:]):
                    priority += 1
                else:
                    regular += 1
    
    return {
        "total_channels": total_channels,
        "total_sources": total_sources,
        "top_priority_sources": top_priority,
        "priority_sources": priority,
        "regular_sources": regular,
        "categories": len(categorized_channels)
    }

def main():
    print("🚀 Starting M3U to JS conversion...")
    print(f"📥 Fetching M3U from: {M3U_URL}")
    
    try:
        # Fetch M3U file
        response = requests.get(M3U_URL, timeout=30)
        response.raise_for_status()
        m3u_content = response.text
        
        if not m3u_content.strip().startswith('#EXTM3U'):
            print("⚠️ Warning: File doesn't start with #EXTM3U")
        
        print("🔍 Parsing M3U content...")
        raw_channels = parse_m3u_file(m3u_content)
        print(f"📊 Found {len(raw_channels)} channel entries")
        
        print("🔄 Merging duplicate channels...")
        merged_channels = merge_channel_sources(raw_channels)
        print(f"📊 After merging: {len(merged_channels)} unique channels")
        
        print("⭐ Prioritizing and filtering sources...")
        print("   Priority: 1. aynascope.net, 2. roarzone.info, 3. gpcdn.net")
        prioritized_channels = prioritize_and_filter_sources(merged_channels)
        print(f"📊 After filtering: {len(prioritized_channels)} channels with valid sources")
        
        print("🏷️ Categorizing channels...")
        categorized = categorize_channels(prioritized_channels)
        
        print("📝 Generating JS output...")
        js_output = generate_js_output(categorized)
        
        # Write to JS file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(js_output)
        
        # Calculate final stats for console
        stats = calculate_statistics(categorized)
        
        print(f"\n✅ SUCCESS!")
        print(f"📁 Output saved to: {OUTPUT_FILE}")
        print(f"📊 Final Statistics:")
        print(f"   • Total channels: {stats['total_channels']}")
        print(f"   • Total sources: {stats['total_sources']}")
        print(f"   • ⭐ Top priority sources: {stats['top_priority_sources']}")
        print(f"   • ⚡ Other priority sources: {stats['priority_sources']}")
        print(f"   • 📡 Regular sources: {stats['regular_sources']}")
        
        print(f"\n📊 Category breakdown:")
        for category in GROUP_ORDER:
            if category in categorized:
                count = len(categorized[category])
                if count > 0:
                    print(f"   • {category}: {count} channels")
        
        # Show sample of JS output
        print(f"\n📝 SAMPLE JS OUTPUT (first few lines):")
        print("-" * 50)
        lines = js_output.split('\n')[:15]
        for line in lines:
            print(line)
        print("...")
        print("-" * 50)
        
    except requests.RequestException as e:
        print(f"❌ Failed to fetch M3U file: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())