import re

with open(r'C:\Users\cashk\OneDrive\Projects\medicare_provider_spending\youngstown_parishes.html', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# Find parish links
parish_links = re.findall(r'href="(https?://doy\.org/parish[^"]*?)"[^>]*>([^<]+)', content)
print(f'Parish links: {len(parish_links)}')
for link, name in parish_links[:80]:
    print(f'  {name.strip()} -> {link}')
if len(parish_links) > 80:
    print(f'  ... and {len(parish_links)-80} more')

# Also try to find h4/h5 tags with parish names
h_tags = re.findall(r'<h[345][^>]*>(.*?)</h[345]>', content, re.DOTALL)
parish_h = [re.sub(r'<[^>]+>', '', h).strip() for h in h_tags if 'St.' in h or 'Holy' in h or 'Our Lady' in h or 'Sacred' in h or 'Immaculate' in h or 'Christ' in h or 'Queen' in h]
print(f'\nParish H-tags: {len(parish_h)}')
for p in parish_h[:80]:
    print(f'  {p}')

# Also look for county headers and parish entries
counties = re.findall(r'(\w+ County Parishes)', content)
print(f'\nCounties: {counties}')

# Look for elementor accordion or similar patterns
accordion = re.findall(r'elementor-tab-title[^>]*>([^<]+)', content)
print(f'\nAccordion tabs: {len(accordion)}')
for a in accordion:
    print(f'  {a.strip()}')

# Search for parish names in any format
all_saints = re.findall(r'(?:St\.\s+\w+(?:\s+\w+)?|Holy\s+\w+(?:\s+\w+)?|Our\s+Lady\s+of\s+\w+(?:\s+\w+)?|Sacred\s+Heart|Immaculate\s+Conception|Christ\s+the\s+King|Queen\s+of\s+\w+)\s*(?:Parish|Church)?', content)
unique_saints = list(set(all_saints))
unique_saints.sort()
print(f'\nUnique parish name patterns: {len(unique_saints)}')
for s in unique_saints[:80]:
    print(f'  {s}')
