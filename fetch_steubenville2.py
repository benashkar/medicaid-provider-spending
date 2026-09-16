import urllib.request
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.5",
}

# Get homepage
req = urllib.request.Request("https://www.diosteub.org/", headers=headers)
resp = urllib.request.urlopen(req, timeout=15)
html = resp.read().decode("utf-8", errors="replace")
print(f"Homepage: {len(html)} bytes")

# Find parish-related links
links = re.findall(r'href="(/[^"]+)"', html)
parish_links = [l for l in links if any(x in l.lower() for x in ['parish', 'find', 'church', 'director', 'locat'])]
print(f"Parish-related links: {parish_links}")

# Find all nav links
all_nav = re.findall(r'href="(/[^"]+)"[^>]*>\s*([^<]+)', html)
for link, text in all_nav:
    t = text.strip()
    if t and any(x in t.lower() for x in ['parish', 'find', 'director', 'locat', 'church']):
        print(f"  Nav: {t} -> {link}")

# Try some common paths
for path in ["/parishes", "/parish-directory", "/find-a-parish", "/our-parishes", "/parish-list", "/parish-finder", "/parish-locations", "/church-directory"]:
    try:
        url = f"https://www.diosteub.org{path}"
        req2 = urllib.request.Request(url, headers=headers)
        resp2 = urllib.request.urlopen(req2, timeout=10)
        data = resp2.read().decode("utf-8", errors="replace")
        print(f"  {path}: {resp2.status} ({len(data)} bytes)")
    except urllib.error.HTTPError as e:
        print(f"  {path}: HTTP {e.code}")
    except Exception as e:
        print(f"  {path}: Error - {e}")

# The eCatholic platform may have a different path structure
# Let's look at what paths exist in the homepage
print("\nAll unique paths from homepage:")
unique_paths = sorted(set(links))
for p in unique_paths[:50]:
    print(f"  {p}")
