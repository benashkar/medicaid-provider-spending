import urllib.request
import urllib.parse
import json
import re

# Step 1: Get fresh page with CSRF token / SPRIG data
url = "https://toledodiocese.org/find-a-parish"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
with urllib.request.urlopen(req, timeout=30) as resp:
    html = resp.read().decode("utf-8", errors="replace")

print(f"Page size: {len(html)}")

# Look for the Sprig/HTMX data endpoint
sprig_matches = re.findall(r'data-hx-get="([^"]+)"', html)
for s in sprig_matches:
    print(f"HX-GET: {s}")

# Look for CSRF token
csrf = re.findall(r'name="CRAFT_CSRF_TOKEN"\s+value="([^"]+)"', html)
for c in csrf:
    print(f"CSRF: {c}")

# Look for hidden input fields
hidden = re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', html)
for name, val in hidden:
    print(f"Hidden: {name}={val[:50]}")

# Look for any parish listings already in HTML
parish_links = re.findall(r'href="([^"]*)"[^>]*>\s*([^<]*(?:St\.|Holy|Our Lady|Sacred|Immaculate|Christ)[^<]*)', html)
print(f"\nParish links in HTML: {len(parish_links)}")
for link, text in parish_links[:20]:
    print(f"  {text.strip()} -> {link}")

# Look for parish data in script tags
script_data = re.findall(r'var\s+(\w+)\s*=\s*(\[{.*?}\])', html[:50000], re.DOTALL)
for name, data in script_data:
    print(f"\nScript var: {name} ({len(data)} chars)")

# Look for any JSON embedded data
json_blocks = re.findall(r'application/json[^>]*>(.*?)</script>', html, re.DOTALL)
for jb in json_blocks[:3]:
    print(f"JSON block: {jb[:200]}")

# Find all <a> tags with parish-like text
all_links = re.findall(r'<a[^>]*href="(/[^"]*)"[^>]*>([^<]+)</a>', html)
parish_names = [(link, text.strip()) for link, text in all_links if any(x in text for x in ['St.', 'Holy', 'Our Lady', 'Sacred', 'Immaculate', 'Christ', 'Queen', 'Blessed', 'Cathedral'])]
print(f"\nParish name links: {len(parish_names)}")
for link, text in parish_names[:30]:
    print(f"  {text} -> {link}")

# Look for the sprig component data
sprig_data = re.findall(r's-val:([^=]+)="([^"]*)"', html)
for name, val in sprig_data:
    print(f"Sprig val: {name}={val}")
