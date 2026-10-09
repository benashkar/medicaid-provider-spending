import subprocess
import re

def curl_get(url):
    result = subprocess.run([
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Accept: text/html,application/xhtml+xml",
        "-H", "Accept-Language: en-US,en;q=0.5",
        "--max-time", "30",
        url
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout

# Fetch the parish finder page
html = curl_get("https://www.diosteub.org/parishfinder")
print(f"Parish finder page: {len(html)} bytes")

# Look for Google Maps or eCatholic parish data
# eCatholic sites typically have the parish data in a specific format

# Look for parish names in the page
parish_names = re.findall(r'<h[2-6][^>]*>([^<]+)</h[2-6]>', html)
print(f"H-tags: {len(parish_names)}")
for p in parish_names[:20]:
    if p.strip():
        print(f"  {p.strip()}")

# Look for the eCatholic parish finder widget
ec_widget = re.findall(r'ecatholic[^"]*parish[^"]*|parish-finder[^"]*|findAnOrg[^"]*', html, re.IGNORECASE)
print(f"\neCatholic widgets: {ec_widget}")

# Look for iframe embeds
iframes = re.findall(r'<iframe[^>]*src="([^"]+)"', html)
for i in iframes:
    print(f"Iframe: {i[:200]}")

# Look for script tags with parish data
scripts = re.findall(r'<script[^>]*src="([^"]*(?:parish|finder|map|org)[^"]*)"', html, re.IGNORECASE)
for s in scripts:
    print(f"Script: {s}")

# Look for any JSON data
json_data = re.findall(r'var\s+\w+\s*=\s*(\[{.*?}\])', html[:50000], re.DOTALL)
for j in json_data[:3]:
    print(f"JSON data: {j[:200]}")

# Look for Google Maps API key and markers
map_data = re.findall(r'google\.maps|findAnOrg|ecatholic.*api|\/api\/.*parish', html, re.IGNORECASE)
print(f"\nMap/API refs: {map_data}")

# Look for eCatholic specific patterns
ec_patterns = re.findall(r'cdn\.ecatholic|ecatholic\.com/[^\s"<]+', html)
ec_unique = sorted(set(ec_patterns))
for p in ec_unique:
    if 'parish' in p.lower() or 'finder' in p.lower() or 'org' in p.lower():
        print(f"eCatholic: {p}")

# Print all unique JS files
js_files = re.findall(r'<script[^>]*src="([^"]+\.js[^"]*)"', html)
for j in js_files:
    if 'ecatholic' in j or 'parish' in j.lower() or 'finder' in j.lower():
        print(f"JS: {j}")

# Check if it's an iframe to another site
print("\nLooking for embedded content...")
embeds = re.findall(r'<iframe[^>]+>', html)
for e in embeds:
    print(f"  {e[:300]}")

# Look at a section of the HTML around "parish"
idx = html.lower().find("parish")
while idx > 0:
    chunk = html[max(0,idx-50):idx+200]
    if 'St.' in chunk or 'Holy' in chunk:
        print(f"\nContext: ...{chunk}...")
        break
    idx = html.lower().find("parish", idx+1)
