
import re

def parse_js():
    with open("developer_main.js", "r") as f:
        content = f.read()
    
    # Find .post(url, data) patterns
    # Since it's minified, it might be like e.post("url",{...})
    # We'll look for .post followed by a string
    
    matches = re.finditer(r'\.post\("([^"]+)"', content)
    
    seen = set()
    print("API Endpoints found in JS:")
    for m in matches:
        url = m.group(1)
        if url not in seen:
            print(f"URL: {url}")
            # Try to grab some context
            start = m.start()
            end = min(start + 200, len(content))
            context = content[start:end]
            print(f"Context: {context}...")
            print("-" * 20)
            seen.add(url)

if __name__ == "__main__":
    parse_js()
