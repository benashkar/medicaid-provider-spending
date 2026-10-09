import subprocess
import re

def curl_get(url):
    result = subprocess.run([
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Accept: text/html,application/xhtml+xml",
        "--max-time", "15",
        url
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout

html = curl_get("https://www.diosteub.org/parishfinder")

# Look for the body baseUrl attribute
base = re.findall(r'baseUrl="([^"]+)"', html)
print(f"BaseUrl: {base}")

# Look for data loading patterns
data_urls = re.findall(r'https?://[^\s"<>]+(?:api|data|json|xml|finder)[^\s"<>]*', html, re.IGNORECASE)
for u in set(data_urls):
    print(f"Data URL: {u}")

# The eCatholic platform uses AJAX to load parish data
# The body tag typically has a baseUrl attribute that's used by the finder.js
# Let's check the body tag
body_tag = re.search(r'<body[^>]*>', html)
if body_tag:
    print(f"\nBody tag: {body_tag.group()[:500]}")

# Look for the finder div
finder_div = re.findall(r'id="finder"[^>]*', html)
for f in finder_div:
    print(f"Finder div: {f[:300]}")

# Look for data embedded in the page
categories_div = re.findall(r'id="categories"(.*?)(?=<div id="[^c]|$)', html, re.DOTALL)
if categories_div:
    print(f"\nCategories section: {len(categories_div[0])} chars")
    # Find sites within
    sites = re.findall(r'class="site"[^>]*(.*?</div>\s*</div>\s*</div>)', categories_div[0], re.DOTALL)
    print(f"Sites: {len(sites)}")
    for s in sites[:3]:
        print(f"  {s[:200]}")
    # Find any content
    content = re.sub(r'<[^>]+>', ' ', categories_div[0])
    content = re.sub(r'\s+', ' ', content).strip()
    print(f"  Text content: {content[:500]}")

# Also check for the deaneries page which may have parish lists
print("\n--- Trying deaneries page ---")
deaneries_html = curl_get("https://www.diosteub.org/deaneries")
print(f"Deaneries page: {len(deaneries_html)} bytes")

# Find parish names in deaneries page
names_d = re.findall(r'>([^<]*(?:St\.|Holy|Our Lady|Sacred|Immaculate|Christ|Queen|Cathedral)[^<]{3,60})<', deaneries_html)
unique_names = sorted(set([n.strip() for n in names_d if n.strip() and len(n.strip()) > 5]))
print(f"Unique parish names: {len(unique_names)}")
for n in unique_names:
    print(f"  {n}")
