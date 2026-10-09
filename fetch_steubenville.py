import urllib.request
import re
import http.cookiejar

# Use cookie jar to maintain session
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.addheaders = [
    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"),
    ("Accept-Language", "en-US,en;q=0.5"),
]

# First get the homepage to establish session
print("Fetching homepage...")
resp = opener.open("https://www.diosteub.org/", timeout=15)
html = resp.read().decode("utf-8", errors="replace")
print(f"Homepage: {resp.status} ({len(html)} bytes)")

# Now try parish-related pages
for path in ["/parishes", "/parish-directory", "/find-a-parish", "/our-parishes", "/parish-locations", "/parish-list"]:
    try:
        url = f"https://www.diosteub.org{path}"
        resp = opener.open(url, timeout=15)
        data = resp.read().decode("utf-8", errors="replace")
        print(f"{path}: {resp.status} ({len(data)} bytes)")
        if resp.status == 200 and len(data) > 1000:
            # Look for parish content
            parish_names = re.findall(r'>([^<]*(?:St\.|Holy|Our Lady|Sacred|Immaculate|Christ)[^<]{3,50})<', data)
            print(f"  Parish names found: {len(parish_names)}")
            for p in parish_names[:5]:
                print(f"    {p.strip()}")
    except urllib.error.HTTPError as e:
        print(f"{path}: HTTP {e.code}")
    except Exception as e:
        print(f"{path}: Error - {e}")

# Look for parish links from the homepage
print("\nLooking for parish links in homepage...")
parish_links = re.findall(r'href="([^"]*)"[^>]*>\s*([^<]*)', html)
for link, text in parish_links:
    text_clean = text.strip()
    if text_clean and any(x in text_clean.lower() for x in ['parish', 'church', 'find a', 'director']):
        print(f"  {text_clean} -> {link}")

# Search for any navigation items
nav_items = re.findall(r'<li[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>', html)
for link, text in nav_items:
    text_clean = text.strip()
    if text_clean:
        print(f"  Nav: {text_clean} -> {link}")
