"""Gemini(Google 검색 그라운딩)에게 Reddit에서 함께 추천된 책을 물어 후보로 저장한다.

Claude의 도구는 Reddit을 열 수 없어서, Reddit과 데이터 계약이 있는 Google 검색을 쓰는 Gemini에 맡긴다.
결과는 '후보 제안'일 뿐이다: 원제·저자 검증(YES24/Goodreads)을 통과한 책만 목록에 올리고, 점수(언급 수)에는 넣지 않는다.

사용법:
  python scripts/gemini_candidates.py tinker "Tinker, Tailor, Soldier, Spy (John le Carré)" [--model gemini-2.5-flash]
결과: data/community/<slug>.gemini.json
"""
import json, os, pathlib, re, sys, time, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
KEY = os.environ.get("GEMINI_API_KEY") or env.get("GEMINI_API_KEY")
if not KEY:
    sys.exit(".env 에 GEMINI_API_KEY 가 없습니다.")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "gemini-2.5-flash"
if "--model" in sys.argv:
    args = [a for a in args if a != model]
slug, seed = args[0], args[1]
API = "https://generativelanguage.googleapis.com/v1beta/models/"

PROMPTS = [
    f'Search Reddit only (use queries starting with site:reddit.com). Find threads where readers recommend books similar to {seed}, '
    'e.g. "books like ...", "best spy novels", "what to read after ...". Use ONLY reddit.com results; ignore every other site.',
    f'Search Reddit only (site:reddit.com r/books, r/suggestmeabook, r/Fantasy, r/printSF, r/thrillers, r/literature). '
    f'Find less obvious, long-tail recommendations commenters gave for readers who loved {seed} — not just the famous classics. '
    'Use ONLY reddit.com results.',
]
FORMAT = ('\n\nAnswer with one book per line, nothing else, in exactly this format:\n'
          'TITLE | AUTHOR | subreddit | short reason the commenters gave\n'
          'Give 25-40 lines. Only include books that actually appear in the Reddit threads you found. Original English titles.')


def call(prompt):
    body = json.dumps({"contents": [{"parts": [{"text": prompt + FORMAT}]}],
                       "tools": [{"google_search": {}}],
                       "generationConfig": {"temperature": 0.2}}).encode()
    req = urllib.request.Request(API + model + ":generateContent", data=body,
                                 headers={"Content-Type": "application/json", "x-goog-api-key": KEY})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Gemini API 오류 {e.code}: {e.read()[:300].decode(errors='replace')}")


rows, chunks_all = [], []
for p in PROMPTS:
    res = call(p)
    cand = (res.get("candidates") or [{}])[0]
    text = "".join(x.get("text", "") for x in (cand.get("content") or {}).get("parts", []))
    gm = cand.get("groundingMetadata") or {}
    chunks = [dict(title=(c.get("web") or {}).get("title", ""), uri=(c.get("web") or {}).get("uri", "")) for c in gm.get("groundingChunks", [])]
    chunks_all.append(dict(queries=gm.get("webSearchQueries", []), chunks=chunks))
    # 각 줄이 어떤 출처(청크)로 뒷받침되는지: groundingSupports 의 segment 텍스트로 매핑
    support = []
    for s in gm.get("groundingSupports", []):
        seg = (s.get("segment") or {}).get("text", "")
        doms = [chunks[i]["title"] for i in s.get("groundingChunkIndices", []) if i < len(chunks)]
        support.append((seg, doms))
    for line in text.splitlines():
        parts = [x.strip(" *-•\t") for x in line.split("|")]
        if len(parts) < 2 or not parts[0] or parts[0].upper() == "TITLE":
            continue
        doms = sorted({d for seg, ds in support if seg and (seg in line or line.strip() in seg) for d in ds})
        rows.append(dict(title=parts[0], author=parts[1], subreddit=parts[2] if len(parts) > 2 else "",
                         reason=parts[3] if len(parts) > 3 else "", cited=doms,
                         reddit_cited=any("reddit" in d.lower() for d in doms), prompt=PROMPTS.index(p)))
    time.sleep(2)

# 같은 책 중복 제거 (제목 정규화)
norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower().replace("the ", ""))
uniq = {}
for r in rows:
    k = norm(r["title"])
    if k in uniq:
        uniq[k]["reddit_cited"] |= r["reddit_cited"]; uniq[k]["cited"] = sorted(set(uniq[k]["cited"]) | set(r["cited"]))
    else:
        uniq[k] = r
out = ROOT / "data" / "community" / f"{slug}.gemini.json"
out.parent.mkdir(parents=True, exist_ok=True)
all_domains = sorted({c["title"] for g in chunks_all for c in g["chunks"]})
out.write_text(json.dumps(dict(seed=seed, model=model, fetched=time.strftime("%Y-%m-%d"), search=chunks_all,
                               domains=all_domains, books=list(uniq.values())), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"모델 {model} | 후보 {len(uniq)}권 | 출처 도메인: {', '.join(all_domains)}")
print(f"Reddit 출처로 뒷받침된 줄: {sum(1 for r in uniq.values() if r['reddit_cited'])}권")
print("저장:", out)
