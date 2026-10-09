import urllib.request
import urllib.parse
import json
import re

# Step 1: Get fresh page and nonce
url = "https://columbuscatholic.org/find-a-parish"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as resp:
    html = resp.read().decode("utf-8", errors="replace")

m = re.search(r'"nonce":"([^"]+)"', html)
if not m:
    print("Could not find nonce")
    exit(1)

nonce = m.group(1)
print(f"Nonce: {nonce}")

# Step 2: Search for parishes - try with "St" to match many
ajax_url = "https://columbuscatholic.org/wp-admin/admin-ajax.php"

all_venues = []
for search_term in ["St", "Holy", "Our", "Sacred", "Immaculate", "Christ", "Queen", "Blessed", "All", "Corpus", "Cathedral", "Resurrection", "Nativity", "Assumption"]:
    data = urllib.parse.urlencode({
        "parish_name": search_term,
        "zipcode": "",
        "city": "",
        "sort_filter": "name",
        "view_type": "list",
        "page": "1",
        "action": "parish_finder_search",
        "nonce": nonce
    }).encode()

    req2 = urllib.request.Request(ajax_url, data=data, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req2, timeout=30) as resp2:
            result = json.loads(resp2.read().decode("utf-8"))

        if result.get("success"):
            venues = result["data"]["venues"]
            total = result["data"].get("total", len(venues))
            if venues:
                print(f"Search '{search_term}': {total} total, {len(venues)} returned")
                for v in venues:
                    name = v.get("name", "")
                    if name and name not in [av.get("name") for av in all_venues]:
                        all_venues.append(v)

                # Get additional pages if needed
                pagination = result["data"].get("pagination", {})
                total_pages = pagination.get("total_pages", 1)
                for page in range(2, min(total_pages + 1, 20)):
                    data_page = urllib.parse.urlencode({
                        "parish_name": search_term,
                        "zipcode": "",
                        "city": "",
                        "sort_filter": "name",
                        "view_type": "list",
                        "page": str(page),
                        "action": "parish_finder_search",
                        "nonce": nonce
                    }).encode()
                    req_page = urllib.request.Request(ajax_url, data=data_page, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req_page, timeout=30) as resp_page:
                        result_page = json.loads(resp_page.read().decode("utf-8"))
                    if result_page.get("success"):
                        for v in result_page["data"]["venues"]:
                            name = v.get("name", "")
                            if name and name not in [av.get("name") for av in all_venues]:
                                all_venues.append(v)
    except Exception as e:
        print(f"Search '{search_term}': Error - {e}")

print(f"\nTotal unique parishes found: {len(all_venues)}")
for v in sorted(all_venues, key=lambda x: x.get("name", "")):
    name = v.get("name", "")
    addr = v.get("address", "")
    city = v.get("city", "")
    state = v.get("state", "")
    phone = v.get("phone", "")
    website = v.get("url", "") or v.get("website", "") or v.get("link", "")
    print(f"{name}|{addr}|{city}, {state}|{phone}|{website}")
