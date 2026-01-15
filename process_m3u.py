#!/usr/bin/env python3
"""
Process M3U file from GitHub and generate optimized channel list with domain priority
"""

import re
import json
import requests
from datetime import datetime
from collections import defaultdict
from urllib.parse import urlparse

# Configuration
M3U_URL = "https://raw.githubusercontent.com/username/repo/main/playlist.m3u"  # Replace with your M3U URL
OUTPUT_FILE = "channels.json"

# YOUR PRIORITY DOMAINS (in order of preference)
PRIORITY_DOMAINS = [
    "aynascope.net",
    "roarzone.info", 
    "owrcovcrpy.gpcdn.net",
    "gpcdn.net",  # Keep this for any other gpcdn.net domains
]

# Domains that require special headers/tokens (will be excluded)
PROBLEMATIC_DOMAINS = [
    "ott-provider.net",
    "stream-url.com",
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
            return 999  # Lowest priority (will be filtered out later)
    
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
            # For your specific domains
            if 'aynascope.net' in domain.lower():
                return "aynascope.net"
            elif 'roarzone.info' in domain.lower():
                return "roarzone.info"
            elif 'gpcdn.net' in domain.lower():
                return "gpcdn.net"
            # For other domains, use last two parts
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
    
    # Check for very long tokens/keys in URL (indicating authentication)
    # Simple heuristic: if URL has very long query parameters
    if '?' in url:
        query = url.split('?')[1]
        # If query parameter value is very long (likely a token)
        for param in query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if len(value) > 100:  # Very long token
                    return True
    
    return False

def parse_m3u_file(content):
    """Parse M3U content and extract channels with multiple sources."""
    channels = []
    current_channel = {}
    
    lines = content.strip().split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for EXTINF line
        if line.startswith('#EXTINF:'):
            # Parse EXTINF line
            extinf_data = line[8:]  # Remove '#EXTINF:'
            
            # Extract logo, group-title, and channel name
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf_data)
            group_match = re.search(r'group-title="([^"]*)"', extinf_data)
            
            # Extract channel name (after last comma)
            comma_pos = extinf_data.rfind(',')
            if comma_pos != -1:
                channel_name = extinf_data[comma_pos + 1:].strip()
            else:
                # Fallback: look for tvg-name
                name_match = re.search(r'tvg-name="([^"]*)"', extinf_data)
                channel_name = name_match.group(1) if name_match else "Unknown"
            
            # Get group/category
            if group_match:
                raw_group = group_match.group(1).strip()
                # Clean group name (lowercase for consistent mapping)
                raw_group_lower = raw_group.lower()
                
                # Map to standardized category
                category = None
                for key, value in CATEGORY_MAPPING.items():
                    if key in raw_group_lower:
                        category = value
                        break
                
                if not category:
                    # Use the original group title as category
                    category = raw_group
            else:
                category = "Others"
            
            # Clean channel name
            channel_name = ' '.join(channel_name.split())
            
            # Get logo URL
            logo_url = logo_match.group(1) if logo_match else ""
            
            # Skip to next non-empty line which should be the URL
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            
            if j < len(lines):
                url = lines[j].strip()
                if url and not url.startswith('#'):
                    # Skip problematic URLs that require headers
                    if has_problematic_pattern(url):
                        print(f"   ⚠️ Skipping problematic URL for {channel_name}")
                        i = j + 1
                        continue
                    
                    # Extract domain for source naming
                    domain = extract_domain(url)
                    
                    # Auto-detect stream type
                    if '.mpd' in url.lower():
                        stream_type = "dash"
                    elif '.m3u8' in url.lower():
                        stream_type = "hls"
                    elif 'm3u8?' in url.lower():
                        stream_type = "hls"
                    elif url.endswith('.m3u'):
                        stream_type = "hls"
                    else:
                        stream_type = "hls"
                    
                    source = {
                        "name": domain,  # Will be renamed later with emoji
                        "url": url,
                        "type": stream_type
                    }
                    
                    # Create channel object
                    current_channel = {
                        "name": channel_name,
                        "category": category,
                        "logo": logo_url,
                        "sources": [source]
                    }
                    
                    channels.append(current_channel)
            
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
            # New channel
            merged_channels[channel_name] = {
                "name": channel["name"],
                "category": channel["category"],
                "logo": channel["logo"],
                "sources": []
            }
        
        # Add all sources from this entry
        for source in channel["sources"]:
            # Check if URL already exists for this channel
            existing_urls = [s["url"] for s in merged_channels[channel_name]["sources"]]
            if source["url"] not in existing_urls:
                merged_channels[channel_name]["sources"].append(source)
        
        # Update logo if current one is better
        if not merged_channels[channel_name]["logo"] and channel["logo"]:
            merged_channels[channel_name]["logo"] = channel["logo"]
    
    return list(merged_channels.values())

def prioritize_and_filter_sources(channels):
    """Prioritize sources and filter out problematic ones."""
    filtered_channels = []
    
    for channel in channels:
        # Filter out problematic sources
        valid_sources = []
        for source in channel["sources"]:
            if not has_problematic_pattern(source["url"]):
                valid_sources.append(source)
        
        if not valid_sources:
            # Skip channel if no valid sources
            print(f"   ⚠️ Skipping {channel['name']} - no valid sources")
            continue
        
        # Sort sources by priority
        valid_sources.sort(key=lambda x: get_domain_priority(x["url"]))
        
        # Rename sources with emoji based on priority
        for source in valid_sources:
            priority = get_domain_priority(source["url"])
            domain = source["name"]
            
            # YOUR PRIORITY DOMAINS get gold star
            if any(priority_domain in source["url"].lower() 
                  for priority_domain in PRIORITY_DOMAINS[:3]):  # First 3 are your top priority
                source["name"] = f"⭐ {domain}"
            elif priority <= 3:  # Other priority domains
                source["name"] = f"⚡ {domain}"
            elif priority == 100:  # Regular HTTPS
                source["name"] = f"🔗 {domain}"
            elif priority == 101:  # HTTP
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
        
        # Standardize category
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
        
        # Remove category from channel object
        channel_copy = channel.copy()
        channel_copy.pop("category", None)
        
        categorized[standardized_category].append(channel_copy)
    
    return categorized

def generate_output(categorized_channels):
    """Generate final JSON output."""
    output = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "version": "1.0",
        "channels": {}
    }
    
    # Add categories in order
    for category in GROUP_ORDER:
        if category in categorized_channels:
            # Sort channels alphabetically
            sorted_channels = sorted(
                categorized_channels[category],
                key=lambda x: x["name"].lower()
            )
            output["channels"][category] = sorted_channels
    
    # Add any remaining categories to "Others"
    for category, channels in categorized_channels.items():
        if category not in output["channels"] and category != "Others":
            if "Others" not in output["channels"]:
                output["channels"]["Others"] = []
            
            sorted_channels = sorted(channels, key=lambda x: x["name"].lower())
            output["channels"]["Others"].extend(sorted_channels)
    
    if "Others" not in output["channels"]:
        output["channels"]["Others"] = []
    
    return output

def calculate_statistics(channels, categorized_channels):
    """Calculate statistics."""
    total_channels = len(channels)
    total_sources = sum(len(ch["sources"]) for ch in channels)
    
    # Count sources by priority level
    top_priority = 0  # Your 3 main domains
    priority = 0      # Other priority domains
    regular = 0       # Regular sources
    
    for channel in channels:
        for source in channel["sources"]:
            url = source["url"].lower()
            if any(domain in url for domain in PRIORITY_DOMAINS[:3]):
                top_priority += 1
            elif any(domain in url for domain in PRIORITY_DOMAINS[3:]):
                priority += 1
            else:
                regular += 1
    
    # Category counts
    category_counts = {}
    for category, ch_list in categorized_channels.items():
        category_counts[category] = len(ch_list)
    
    return {
        "total_channels": total_channels,
        "total_sources": total_sources,
        "top_priority_sources": top_priority,
        "priority_sources": priority,
        "regular_sources": regular,
        "avg_sources_per_channel": round(total_sources / total_channels, 2) if total_channels > 0 else 0,
        "categories": len(categorized_channels),
        "category_counts": category_counts
    }

def main():
    print("🚀 Starting M3U processing...")
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
        print("   Priority order: 1. aynascope.net, 2. roarzone.info, 3. gpcdn.net")
        prioritized_channels = prioritize_and_filter_sources(merged_channels)
        print(f"📊 After filtering: {len(prioritized_channels)} channels with valid sources")
        
        print("🏷️ Categorizing channels...")
        categorized = categorize_channels(prioritized_channels)
        
        print("📝 Generating JSON output...")
        output_data = generate_output(categorized)
        
        # Calculate statistics
        stats = calculate_statistics(prioritized_channels, categorized)
        output_data["statistics"] = stats
        output_data["priority_domains"] = PRIORITY_DOMAINS
        
        # Write to file
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ SUCCESS!")
        print(f"📁 Output saved to: {OUTPUT_FILE}")
        print(f"📊 Statistics:")
        print(f"   • Total channels: {stats['total_channels']}")
        print(f"   • Total sources: {stats['total_sources']}")
        print(f"   • ⭐ Top priority sources: {stats['top_priority_sources']}")
        print(f"   • ⚡ Other priority sources: {stats['priority_sources']}")
        print(f"   • 📡 Regular sources: {stats['regular_sources']}")
        print(f"   • Average sources per channel: {stats['avg_sources_per_channel']}")
        
        print(f"\n📊 Category breakdown:")
        for category in GROUP_ORDER:
            if category in output_data["channels"]:
                count = len(output_data["channels"][category])
                if count > 0:
                    print(f"   • {category}: {count} channels")
        
        # Show example output
        print(f"\n📝 EXAMPLE OUTPUT:")
        if prioritized_channels:
            # Find a channel with multiple priority sources
            example_channel = None
            for channel in prioritized_channels:
                if len(channel["sources"]) >= 2:
                    example_channel = channel
                    break
            
            if example_channel:
                print(f'   Channel: {example_channel["name"]}')
                print(f'   Logo: {example_channel["logo"][:50]}...' if len(example_channel["logo"]) > 50 else f'   Logo: {example_channel["logo"]}')
                print(f'   Sources:')
                for i, source in enumerate(example_channel["sources"][:3], 1):
                    print(f'     {i}. {source["name"]}')
        
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