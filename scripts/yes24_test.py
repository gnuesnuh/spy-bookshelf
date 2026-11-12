"""YES24 Open API로 원제·번역서·전자책 매칭을 시험한다. 실행: python scripts/yes24_test.py"""
import json, os, pathlib, sys, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
key = os.environ.get("YES24_API_KEY")
env = ROOT / ".env"
if not key and env.exists():
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("YES24_API_KEY="):
            key = line.split("=", 1)[1].strip().strip('"')
if not key:
    sys.exit(".env에 YES24_API_KEY가 없습니다.")

# (검색어, 카테고리, 확인할 원제 키워드)
TESTS = [
    ("독살로 읽는 세계사", "BOOK", "royal art of poison"),
    ("엘리너 허먼", "BOOK", "royal art of poison"),
    ("데버라 블룸", "BOOK", "poisoner"),
    ("Poisoner's Handbook", "BOOK", "poisoner"),
    ("닐 브래드버리", "BOOK", "taste for poison"),
    ("A Taste for Poison", "BOOK", "taste for poison"),
    ("죽이는 화학", "BOOK", "arsenic"),
]
FIELDS = ["title", "author", "publisher", "publishDate", "originalTitle", "originalTranslation",
          "itemStatus", "starScore", "salePoint", "eBookLink", "link"]

def search(q, cat):
    url = ("https://apis.yes24.com/v1/goods/itemList?detail=Y&pageSize=10&category=" + cat
           + "&query=" + urllib.parse.quote(q))
    req = urllib.request.Request(url, headers={"X-Api-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.loads(e.read() or b"{}")

out = []
for q, cat, want in TESTS:
    d = search(q, cat)
    items = (d.get("data") or {}).get("items") or []
    print(f"\n=== {q} [{cat}] → {len(items)}건 {'' if d.get('success') else d.get('errorCode')}")
    for i in items:
        orig = (i.get("originalTitle") or "")
        hit = "✅" if want in orig.lower() else "  "
        print(f" {hit} {i.get('title')} / {i.get('author')} / {i.get('publisher')} {i.get('publishDate')}"
              f" | 원제={orig or '-'} | 번역={i.get('originalTranslation')} | {i.get('itemStatus')}"
              f" | ★{i.get('starScore')} | 전자책={'O' if i.get('eBookLink') else '-'}")
        out.append({"query": q, **{k: i.get(k) for k in FIELDS}})

p = ROOT / "data" / "cache" / "yes24_test.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n결과 저장: {p}")
