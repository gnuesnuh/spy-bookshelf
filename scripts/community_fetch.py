"""Reddit 대안 커뮤니티에서 추천 댓글을 모아 data/community/<slug>.json 으로 저장한다.

소스 (2026-11-13 접속 확인)
  hn        Hacker News — Algolia 검색 API (댓글·글). 비즈니스·기술·논픽션에 강함
  discourse Straight Dope 등 Discourse 포럼 — /search.json, 스레드 /t/<id>.json
  lemmy     lemmy.world — /api/v3/search (댓글)

사용법:
  python scripts/community_fetch.py barbarians "barbarians at the gate" "liar's poker"
  python scripts/community_fetch.py tinker "tinker tailor" "spy novels" --only hn,discourse

원문은 책 이름 집계와 요약에만 쓰고 결과물에 그대로 싣지 않는다. 요청 사이 1.5초 대기.
Reddit은 공식 API(OAuth) 준비 후 추가 예정(docs/PLAN.md).
"""
import json, pathlib, re, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
UA = "books-research/0.1 (personal, non-commercial)"
DISCOURSE = ["https://boards.straightdope.com"]
LEMMY = "https://lemmy.world"


def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.load(r)
        time.sleep(1.5)
        return data
    except Exception as e:  # 실패한 소스는 건너뛰고 기록만 남긴다
        print(f"  ! {url[:70]} {e}")
        return None


def strip(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def hn(q):
    out = []
    for tag in ("comment", "story"):
        d = get("https://hn.algolia.com/api/v1/search?hitsPerPage=50&tags=" + tag + "&query=" + urllib.parse.quote(q))
        for h in (d or {}).get("hits", []):
            text = strip(h.get("comment_text") or h.get("story_text") or h.get("title"))
            if text:
                out.append(dict(source="hn", url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                                thread=h.get("story_title") or h.get("title"), points=h.get("points"), text=text))
    return out


def discourse(q):
    out = []
    for base in DISCOURSE:
        d = get(base + "/search.json?q=" + urllib.parse.quote(q))
        for t in ((d or {}).get("topics") or [])[:5]:
            th = get(f"{base}/t/{t['id']}.json")
            for p in ((th or {}).get("post_stream") or {}).get("posts", []):
                out.append(dict(source="discourse", url=f"{base}/t/{t['id']}/{p.get('post_number')}",
                                thread=t.get("title"), points=p.get("score"), text=strip(p.get("cooked"))))
    return out


def lemmy(q):
    d = get(f"{LEMMY}/api/v3/search?type_=Comments&limit=50&q=" + urllib.parse.quote(q))
    return [dict(source="lemmy", url=c["comment"]["ap_id"], thread=c["post"]["name"],
                 points=(c.get("counts") or {}).get("score"), text=c["comment"]["content"])
            for c in (d or {}).get("comments", [])]


SOURCES = dict(hn=hn, discourse=discourse, lemmy=lemmy)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
only = next((a.split("=", 1)[1] if "=" in a else sys.argv[sys.argv.index(a) + 1]
             for a in sys.argv if a.startswith("--only")), "hn,discourse,lemmy")
if "--only" in sys.argv:
    args = [a for a in args if a != only]
slug, queries = args[0], args[1:]
items, seen = [], set()
for q in queries:
    for name in only.split(","):
        got = SOURCES[name](q)
        print(f"{name:9} {q!r}: {len(got)}")
        for it in got:
            if it["url"] not in seen:
                seen.add(it["url"]); items.append(dict(it, query=q))
out = ROOT / "data" / "community" / f"{slug}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(queries=queries, fetched=time.strftime("%Y-%m-%d"), items=items), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"저장: {out} ({len(items)}건)")
