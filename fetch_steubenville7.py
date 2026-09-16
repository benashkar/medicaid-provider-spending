import subprocess
import re

def curl_get(url):
    result = subprocess.run([
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Accept: text/html,application/xhtml+xml",
        "--max-time", "30",
        url
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout

html = curl_get("https://www.diosteub.org/parishfinder")

# The page has parish data but in a single long line
# Let's split on common delimiters and find parish entries
# The text showed: "Assumption of the Blessed Virgin Mary Barnesville X phone directions"
# This suggests the HTML has structured data, just compressed

# Find all site blocks - eCatholic format
# Try to find name spans
names = re.findall(r'class="name"[^>]*>\s*([^<]+)', html)
print(f"Names via class=name: {len(names)}")
for n in names:
    print(f"  {n.strip()}")

# Try the full Google Maps search links to extract parish names and addresses
gmaps = re.findall(r'google\.com/maps/search/\?api=1&(?:amp;)?query=([^"&<]+)', html)
print(f"\nGoogle Maps queries: {len(gmaps)}")
for g in gmaps[:50]:
    from urllib.parse import unquote
    print(f"  {unquote(g)}")

# Find phone numbers
phones = re.findall(r'P:\s*\((\d{3})\)\s*(\d{3})-(\d{4})', html)
print(f"\nPhones: {len(phones)}")

# Find all addresses
addrs = re.findall(r'(\d+\s+[A-Z][^,]+,\s*[^,]+,\s*OH,?\s*\d{5})', html)
print(f"\nAddresses: {len(addrs)}")
for a in addrs[:50]:
    print(f"  {a}")

# Try to find the full parish entries
# Pattern: name X phone directions name address P: phone
entries = re.findall(r'>([\w\s.\']+?(?:Parish|Church|Mission|Chapel)?)\s*(?:<[^>]*>)*\s*(\d+[^,<]+,\s*[^,<]+,\s*OH,?\s*\d{5})\s*(?:<[^>]*>)*\s*P:\s*\((\d{3})\)\s*(\d{3})-(\d{4})', html, re.DOTALL)
print(f"\nFull entries: {len(entries)}")
for e in entries[:30]:
    print(f"  {e[0].strip()} | {e[1].strip()} | ({e[2]}) {e[3]}-{e[4]}")
