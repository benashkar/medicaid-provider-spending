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

html = curl_get("https://www.diosteub.org/parishfinder")
print(f"Page size: {len(html)} bytes")

# The eCatholic finder uses .site divs with data attributes
# Find all site divs
site_blocks = re.findall(r'<div[^>]*class="site"[^>]*data-latitude="([^"]*)"[^>]*data-longitude="([^"]*)"[^>]*>(.*?)</div>\s*</div>\s*</div>', html, re.DOTALL)
print(f"Site blocks with coords: {len(site_blocks)}")

# Try broader pattern
site_blocks2 = re.findall(r'class="site"', html)
print(f"site class occurrences: {len(site_blocks2)}")

# Find the name elements within site blocks
names = re.findall(r'class="name"[^>]*>([^<]+)', html)
print(f"\nParish names: {len(names)}")
for n in names:
    print(f"  {n.strip()}")

# Find addresses
addresses = re.findall(r'class="address"[^>]*>(.*?)</(?:div|span|p)', html, re.DOTALL)
print(f"\nAddresses: {len(addresses)}")
for a in addresses[:30]:
    clean = re.sub(r'<[^>]+>', ' ', a).strip()
    if clean:
        print(f"  {clean}")

# Find phone numbers
phones = re.findall(r'class="phone"[^>]*>([^<]+)', html)
print(f"\nPhones: {len(phones)}")
for p in phones[:30]:
    print(f"  {p.strip()}")

# Find website URLs
websites = re.findall(r'class="website"[^>]*>\s*<a[^>]*href="([^"]+)"', html)
print(f"\nWebsites: {len(websites)}")
for w in websites[:30]:
    print(f"  {w}")

# Also look for category headers
categories = re.findall(r'class="categoryTitle"[^>]*>([^<]+)', html)
print(f"\nCategories: {len(categories)}")
for c in categories:
    print(f"  {c.strip()}")
