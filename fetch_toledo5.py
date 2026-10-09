import urllib.request
import re
import html as html_mod

url = "https://toledodiocese.org/find-a-parish"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Get the page
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as resp:
    page = resp.read().decode("utf-8", errors="replace")

# Extract all article blocks
articles = re.findall(r'<article[^>]*>(.*?)</article>', page, re.DOTALL)
print(f"Articles: {len(articles)}")

all_parishes = []
for a in articles:
    names = re.findall(r'<h[2-6][^>]*>\s*(?:<a[^>]*>)?([^<]+)', a)
    addrs = re.findall(r'(\d+[^<,]+(?:OH|Ohio)\s+\d{5})', a)
    phones = re.findall(r'(\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4})', a)
    links = re.findall(r'href="(/parish[^"]*|https?://[^"]*)"', a, re.IGNORECASE)
    parish_name = names[0].strip() if names else ""
    if parish_name:
        all_parishes.append({
            "name": parish_name,
            "address": addrs[0] if addrs else "",
            "phone": phones[0] if phones else "",
            "link": links[0] if links else ""
        })

print(f"Parishes from articles: {len(all_parishes)}")
for p in all_parishes:
    print(f"  {p['name']} | {p['address']} | {p['phone']}")

# Check for pagination info
pages_match = re.findall(r's-val:page="(\d+)"', page)
max_page = max([int(p) for p in pages_match]) if pages_match else 1
print(f"\nMax page from pagination: {max_page}")
print(f"Estimated total parishes: {len(all_parishes)} per page x {max_page} pages = ~{len(all_parishes) * max_page}")

# Also check for the total count displayed on the page
total_match = re.findall(r'(\d+)\s*(?:total|results|parishes|found)', page, re.IGNORECASE)
for t in total_match:
    print(f"Total mentioned: {t}")

# Look for "Showing X of Y" or similar
showing = re.findall(r'(?:Showing|Displaying|of)\s+(\d+)', page)
for s in showing:
    print(f"Showing/of: {s}")

# Also check result count headers
result_header = re.findall(r'find-a-results-header[^>]*>([^<]*)', page)
for rh in result_header:
    if rh.strip():
        print(f"Results header: {rh.strip()}")
