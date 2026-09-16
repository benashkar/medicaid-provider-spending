import subprocess
import re

def curl_get(url):
    result = subprocess.run([
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "-H", "Accept: text/html,application/xhtml+xml",
        "-H", "Accept-Language: en-US,en;q=0.5",
        "--max-time", "15",
        url
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.stdout

# Get homepage
html = curl_get("https://www.diosteub.org/")
print(f"Homepage: {len(html)} bytes")

# Find all nav links
all_links = re.findall(r'href="(/[^"]+)"', html)
print(f"Total links: {len(all_links)}")

# Print all unique paths
unique = sorted(set(all_links))
for p in unique[:60]:
    print(f"  {p}")

# Find parish-related links
for link in unique:
    if any(x in link.lower() for x in ["parish", "find", "church", "direct", "locat"]):
        print(f"  PARISH: {link}")

# Try common paths
print("\nTrying common paths:")
for path in ["/parishes", "/parish-directory", "/find-a-parish", "/our-parishes"]:
    result = subprocess.run([
        "curl", "-s", "-L",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "-H", "Accept: text/html,application/xhtml+xml",
        "--max-time", "10",
        "-o", "/dev/null", "-w", "%{http_code}",
        f"https://www.diosteub.org{path}"
    ], capture_output=True, text=True)
    print(f"  {path}: {result.stdout}")
