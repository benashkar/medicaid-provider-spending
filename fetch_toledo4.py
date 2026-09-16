import urllib.request
import urllib.parse
import json
import re
import html

base_url = "https://toledodiocese.org/find-a-parish"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
}

# Get initial page
req = urllib.request.Request(base_url, headers=headers)
with urllib.request.urlopen(req, timeout=30) as resp:
    page_html = resp.read().decode("utf-8", errors="replace")
    resp_cookies = resp.headers.get_all("Set-Cookie")

# Extract cookies
cookie_str = ""
if resp_cookies:
    for c in resp_cookies:
        parts = c.split(";")[0]
        cookie_str += parts + "; "

# Extract CSRF token
csrf_match = re.search(r'name="CRAFT_CSRF_TOKEN"\s+value="([^"]+)"', page_html)
csrf = csrf_match.group(1) if csrf_match else ""

# Extract the full HX-VALS with sprig config
hx_vals_raw = re.findall(r'data-hx-vals="([^"]*)"', page_html)
# Get the first one which contains sprig:siteId and sprig:template
sprig_config = {}
for v in hx_vals_raw:
    decoded = html.unescape(v)
    try:
        parsed = json.loads(decoded)
        if "sprig:siteId" in parsed or "sprig:template" in parsed:
            sprig_config.update(parsed)
    except:
        pass

print(f"Sprig config keys: {list(sprig_config.keys())}")

# Extract the sprig:config value
sprig_config_match = re.findall(r'data-sprig-config="([^"]*)"', page_html)
if sprig_config_match:
    print(f"Sprig config: {sprig_config_match[0][:100]}")

# Now make the actual Sprig request
sprig_url = "https://toledodiocese.org/index.php?p=actions/sprig-core/components/render"

all_parishes = []
for page_num in range(1, 20):
    try:
        # Build the POST data
        post_data = {
            "CRAFT_CSRF_TOKEN": csrf,
            "page": str(page_num),
            "query": "",
        }
        # Add sprig config params
        post_data.update(sprig_config)

        encoded_data = urllib.parse.urlencode(post_data).encode()

        sprig_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html, */*",
            "HX-Request": "true",
            "HX-Target": ".find-a-results",
            "Content-Type": "application/x-www-form-urlencoded",
            "Cookie": cookie_str,
            "Referer": base_url,
            "X-Requested-With": "XMLHttpRequest",
        }

        req_sprig = urllib.request.Request(sprig_url, data=encoded_data, headers=sprig_headers)
        with urllib.request.urlopen(req_sprig, timeout=15) as resp_sprig:
            sprig_html = resp_sprig.read().decode("utf-8", errors="replace")

        # Extract parish names from the response
        # Look for parish entries
        parish_entries = re.findall(r'<h[2-6][^>]*>\s*<a[^>]*>([^<]+)</a>\s*</h[2-6]>', sprig_html)
        if not parish_entries:
            parish_entries = re.findall(r'<h[2-6][^>]*>([^<]+)</h[2-6]>', sprig_html)
            parish_entries = [p.strip() for p in parish_entries if p.strip() and len(p.strip()) > 3]

        # Also extract addresses and phones
        addresses = re.findall(r'(\d+[^,<]+,\s*OH\s+\d{5})', sprig_html)
        phones = re.findall(r'(\(\d{3}\)\s*\d{3}[-.]\d{4}|\d{3}[-.]\d{3}[-.]\d{4})', sprig_html)

        if not parish_entries:
            # Try broader match
            parish_entries = re.findall(r'>([^<]{5,80}(?:Parish|Church))[^<]*<', sprig_html)

        if not parish_entries and page_num > 1:
            print(f"Page {page_num}: No parishes found, stopping")
            break

        print(f"Page {page_num}: {len(parish_entries)} parishes, {len(addresses)} addresses")
        for p in parish_entries:
            cleaned = p.strip()
            if cleaned and cleaned not in all_parishes:
                all_parishes.append(cleaned)

    except urllib.error.HTTPError as e:
        print(f"Page {page_num}: HTTP {e.code}")
        if page_num == 1:
            # Print error body
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                print(f"Error body: {err_body[:500]}")
            except:
                pass
        break
    except Exception as e:
        print(f"Page {page_num}: Error - {e}")
        break

print(f"\nTotal unique parishes: {len(all_parishes)}")
for p in sorted(all_parishes):
    print(f"  {p}")
