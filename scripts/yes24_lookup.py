"""사용: python scripts/yes24_lookup.py "검색어" ["검색어" ...]  — YES24 국내도서 검색, 원제/역자/전자책 표시"""
import json, os, pathlib, sys, urllib.parse, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
key = os.environ.get("YES24_API_KEY") or next((l.split("=",1)[1].strip().strip('"') for l in (ROOT/".env").read_text(encoding="utf-8").splitlines() if l.startswith("YES24_API_KEY=")), "")
for q in sys.argv[1:]:
    url = "https://apis.yes24.com/v1/goods/itemList?detail=Y&pageSize=8&category=BOOK&query=" + urllib.parse.quote(q)
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"X-Api-Key": key}), timeout=20))
    except urllib.error.HTTPError as e:
        d = json.loads(e.read() or b"{}")
    items = (d.get("data") or {}).get("items") or []
    print(f"\n=== {q} → {len(items)}건")
    for i in items:
        print(f"  {i.get('title')} | {i.get('author')} | {i.get('publisher')} {i.get('publishDate')} | 원제={i.get('originalTitle') or '-'} | {i.get('itemStatus')} | ★{i.get('starScore')} | 판매지수={i.get('salePoint')} | eBook={'O' if i.get('eBookLink') else '-'} | {i.get('link')}")
