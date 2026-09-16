import urllib.request
import urllib.parse
import json
import re

base_url = "https://toledodiocese.org/find-a-parish"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Get initial page to find CSRF token and sprig config
req = urllib.request.Request(base_url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as resp:
    html = resp.read().decode("utf-8", errors="replace")
    cookies = resp.headers.get_all("Set-Cookie")

# Extract cookies
cookie_str = ""
if cookies:
    for c in cookies:
        parts = c.split(";")[0]
        cookie_str += parts + "; "
    print(f"Cookies: {cookie_str[:100]}")

# Extract CSRF token
csrf_match = re.search(r'name="CRAFT_CSRF_TOKEN"\s+value="([^"]+)"', html)
csrf = csrf_match.group(1) if csrf_match else ""
print(f"CSRF: {csrf[:30]}...")

# Extract the sprig component hash/config
# Look for data-hx-vals or sprig-encoded data
hx_vals = re.findall(r'data-hx-vals="([^"]*)"', html)
for v in hx_vals[:3]:
    print(f"HX-VALS: {v[:200]}")

# Look for the sprig component ID / encoded component
sprig_id = re.findall(r'sprig:id="([^"]*)"', html)
for s in sprig_id[:3]:
    print(f"SPRIG ID: {s}")

# Let's try a different approach - search the sitemap
print("\n--- Trying sitemap ---")
sitemap_url = "https://toledodiocese.org/sitemap.xml"
try:
    req_sm = urllib.request.Request(sitemap_url, headers=headers)
    with urllib.request.urlopen(req_sm, timeout=15) as resp_sm:
        sitemap = resp_sm.read().decode("utf-8", errors="replace")

    # Find all parish-related URLs
    urls = re.findall(r'<loc>([^<]*parish[^<]*)</loc>', sitemap, re.IGNORECASE)
    print(f"Parish URLs in sitemap: {len(urls)}")
    for u in urls[:10]:
        print(f"  {u}")

    # Also look for sub-sitemaps
    sub_sitemaps = re.findall(r'<loc>([^<]*sitemap[^<]*)</loc>', sitemap, re.IGNORECASE)
    print(f"\nSub-sitemaps: {len(sub_sitemaps)}")
    for s in sub_sitemaps:
        print(f"  {s}")
except Exception as e:
    print(f"Sitemap error: {e}")

# Try the Craft CMS entries endpoint
print("\n--- Trying Craft entries ---")
for path in ["/api/parishes", "/api/parish", "/api/entries", "/parishes.json", "/find-a-parish.json"]:
    try:
        test_url = f"https://toledodiocese.org{path}"
        req_test = urllib.request.Request(test_url, headers=headers)
        with urllib.request.urlopen(req_test, timeout=10) as resp_test:
            data = resp_test.read().decode("utf-8", errors="replace")
            print(f"{path}: {resp_test.status} ({len(data)} bytes)")
            if len(data) < 2000:
                print(f"  {data[:500]}")
    except urllib.error.HTTPError as e:
        print(f"{path}: {e.code}")
    except Exception as e:
        print(f"{path}: Error - {e}")

# Try fetching all pages via the sprig endpoint
print("\n--- Trying Sprig pagination ---")
sprig_url = "https://toledodiocese.org/index.php?p=actions/sprig-core/components/render"

# Try to get the encoded body from the initial page
# Look for the full sprig config
sprig_full = re.findall(r'<div[^>]*class="find-a-results"[^>]*data-[^>]*>', html)
for s in sprig_full:
    print(f"Results div: {s[:500]}")

# Try the Sprig endpoint directly with pagination
for page in range(1, 3):
    try:
        sprig_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
            "HX-Request": "true",
            "HX-Target": ".find-a-results",
            "Cookie": cookie_str,
            "Referer": base_url,
        }
        params = urllib.parse.urlencode({
            "page": str(page),
            "query": "",
            "CRAFT_CSRF_TOKEN": csrf
        })
        full_url = f"{sprig_url}&{params}"
        req_sprig = urllib.request.Request(full_url, headers=sprig_headers)
        with urllib.request.urlopen(req_sprig, timeout=15) as resp_sprig:
            sprig_html = resp_sprig.read().decode("utf-8", errors="replace")
            print(f"\nPage {page}: {len(sprig_html)} bytes")
            # Extract parish names
            names = re.findall(r'<h[2-6][^>]*>([^<]+)</h[2-6]>', sprig_html)
            for n in names:
                if n.strip():
                    print(f"  {n.strip()}")
            # Extract any parish entries
            entries = re.findall(r'class="find-a-result[^"]*"[^>]*>(.*?)</(?:div|article)', sprig_html, re.DOTALL)
            print(f"  Entries: {len(entries)}")
    except Exception as e:
        print(f"Page {page}: Error - {e}")
