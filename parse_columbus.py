import sys, re, html

c = sys.stdin.read()

# Find iframe src
iframes = re.findall(r'<iframe[^>]*src="([^"]+)"', c)
for i in iframes:
    print(f'IFRAME: {i[:300]}')

# Find Google Maps embed
gmaps = re.findall(r'google\.com/maps[^\s"<]*', c)
for g in gmaps[:5]:
    print(f'GMAP: {g[:300]}')

# Find any map related scripts
scripts_src = re.findall(r'<script[^>]*src="([^"]*(?:map|parish|location)[^"]*)"', c, re.IGNORECASE)
for s in scripts_src:
    print(f'SCRIPT: {s}')

# Find all h-tags with content
h_tags = re.findall(r'<h[2345][^>]*>(.*?)</h[2345]>', c, re.DOTALL)
for h in h_tags:
    clean = re.sub(r'<[^>]+>', '', h).strip()
    if clean and 3 < len(clean) < 100:
        print(f'H: {clean}')

# Find links containing parish
parish_links = re.findall(r'href="([^"]*parish[^"]*)"[^>]*>([^<]*)<', c, re.IGNORECASE)
print(f'\nParish links: {len(parish_links)}')
for link, text in parish_links[:20]:
    print(f'  {text.strip()} -> {link}')

# Look for elementor list or accordion
accordion = re.findall(r'elementor-accordion-title[^>]*>([^<]+)', c)
print(f'\nAccordion: {len(accordion)}')
for a in accordion[:20]:
    print(f'  {a.strip()}')

# Look for any JSON-like parish data
json_blocks = re.findall(r'"parish(?:_name|Name|es)"[^}]*', c[:100000])
print(f'\nJSON parish blocks: {len(json_blocks)}')
