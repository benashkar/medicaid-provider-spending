import urllib.request
import urllib.parse
import json
import re

# The Toledo diocese uses CraftCMS with Sprig components
# The parish data is loaded via HTMX/Sprig AJAX calls
# Let's try to get the data by examining the rendered HTML more carefully

url = "https://toledodiocese.org/find-a-parish"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml"
})
with urllib.request.urlopen(req, timeout=30) as resp:
    html = resp.read().decode("utf-8", errors="replace")

# The page already has some parish data rendered server-side
# Look for parish result cards/entries
# Find all instances of parish names and addresses
results = re.findall(r'<div class="result[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
print(f"Result divs: {len(results)}")

# Try to find the parish entries in the HTML
# Look for the specific structure
entries = re.findall(r'class="find-a-result[^"]*"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
print(f"Find-a-result divs: {len(entries)}")

# Let's look for the full rendered content
# Find all text between card/entry boundaries
parish_blocks = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
print(f"Article blocks: {len(parish_blocks)}")

# Try another approach - the data is in the initial render
# Let me find all parish data by looking for address patterns
addresses = re.findall(r'(\d+\s+[A-Z][^,<]+,\s*OH\s+\d{5})', html)
print(f"Ohio addresses: {len(addresses)}")
for a in addresses[:20]:
    print(f"  {a}")

# Find all parish-like headings
headings = re.findall(r'<h[2-5][^>]*>\s*<a[^>]*>([^<]+)</a>', html)
print(f"\nHeadings with links: {len(headings)}")
for h in headings[:20]:
    print(f"  {h.strip()}")

# Let's just look at what's rendered on the page
# The Sprig component likely renders parish cards
# Let me look for a broader pattern
cards = re.findall(r'find-a-results(.*)', html, re.DOTALL)
if cards:
    card_text = cards[0][:10000]
    names = re.findall(r'>([^<]*(?:St\.|Holy|Our Lady|Sacred|Immaculate|Christ|Queen|Blessed|Cathedral)[^<]*)<', card_text)
    print(f"\nParish names in results section: {len(names)}")
    for n in names:
        if n.strip():
            print(f"  {n.strip()}")

# Finally, try to extract from the full page
all_parish_names = re.findall(r'>([^<]*(?:St\.\s|Holy\s|Our\sLady|Sacred\s|Immaculate\s|Christ\s|Queen\s|Blessed\s|Cathedral)[^<]{3,50})<', html)
unique_names = list(set([n.strip() for n in all_parish_names if n.strip() and 'function' not in n.lower()]))
unique_names.sort()
print(f"\nAll unique parish-like names: {len(unique_names)}")
for n in unique_names:
    print(f"  {n}")

# Try to get the Sprig data by simulating the AJAX call
# Look for required SPRIG headers/params
sprig_encoded = re.findall(r'sprig:encoded-body="([^"]*)"', html)
print(f"\nSprig encoded bodies: {len(sprig_encoded)}")

# Look for CSRF tokens
csrf_matches = re.findall(r'name="([^"]*csrf[^"]*)"[^>]*value="([^"]*)"', html, re.IGNORECASE)
for name, val in csrf_matches:
    print(f"CSRF: {name}={val[:30]}...")

sprig_config = re.findall(r'data-sprig-config="([^"]*)"', html)
for s in sprig_config:
    print(f"Sprig config: {s[:200]}")
