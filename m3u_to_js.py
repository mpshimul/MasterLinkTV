import sys
import re
import json

def parse_m3u_to_js(m3u_filename, js_output="channels.js"):
    channels = []
    
    with open(m3u_filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_extinf = None

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            current_extinf = line
            continue

        if line.startswith("#"):
            continue  # skip other comments

        if current_extinf and line.startswith("http"):
            # Parse #EXTINF line
            extinf = current_extinf
            
            # Extract group-title (optional)
            group_match = re.search(r'group-title="([^"]*)"', extinf)
            group = group_match.group(1) if group_match else ""

            # Extract tvg-logo (optional)
            logo_match = re.search(r'tvg-logo="([^"]*)"', extinf)
            logo = logo_match.group(1) if logo_match else ""

            # Extract channel name (after last comma)
            parts = extinf.split(',', 1)
            name = parts[1] if len(parts) > 1 else "Unknown"

            channels.append({
                "group": group,
                "name": name,
                "stream": line,
                "logo": logo
            })
            current_extinf = None

    # Write to JS file: `const channels = [ ... ];`
    with open(js_output, 'w', encoding='utf-8') as f:
        js_content = "const channels = " + json.dumps(channels, indent=2, ensure_ascii=False) + ";\n"
        f.write(js_content)

    print(f"✅ Successfully wrote {len(channels)} channels to {js_output}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python m3u_to_js.py <input.m3u> [output.js]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "channels.js"

    parse_m3u_to_js(input_file, output_file)
