import sys
try:
    from googlesearch import search
    results = search("site:undiksha.ac.id berita terbaru hari ini", advanced=True, num_results=3)
    for r in results:
        print(f"Title: {getattr(r, 'title', 'No Title')}")
        print(f"Desc: {getattr(r, 'description', 'No Desc')}")
        print(f"URL: {getattr(r, 'url', 'No URL')}")
        print("---")
except Exception as e:
    print(f"Error: {e}")
