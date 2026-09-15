import sys
try:
    from ddgs import DDGS
    print("Initializing DDGS...")
    with DDGS() as ddgs:
        results = ddgs.text("site:undiksha.ac.id berita", max_results=3)
        print(results)
except Exception as e:
    print(f"Error: {e}")
