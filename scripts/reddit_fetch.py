"""Reddit 추천 스레드를 내 PC에서 직접 내려받아 data/reddit/<slug>.json 으로 저장한다.

이 스크립트는 사용자 본인의 Windows PC 터미널에서 실행한다.
(Claude 쪽 도구와 연결된 셸은 Reddit이 403으로 막으므로 여기서 돌리지 않는다.)

사용법:
  python scripts/reddit_fetch.py tinker "books like tinker tailor soldier spy" "best spy novels"
    → r/books 등에서 검색어마다 상위 스레드를 찾고, 각 스레드의 댓글까지 저장

준비: .env 에 REDDIT_USER_AGENT=python:books-research:v1.0 (by /u/내레딧아이디)
규칙: 공개 .json 엔드포인트, 요청 사이 7초 대기(분당 10회 이하), 개인 비상업 용도.
"""
import json, os, pathlib, sys, time, urllib.parse, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
if (ROOT / ".env").exists():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
UA = os.environ.get("REDDIT_USER_AGENT") or env.get("REDDIT_USER_AGENT")
if not UA or "내레딧아이디" in UA:
    sys.exit(".env 에 REDDIT_USER_AGENT=python:books-research:v1.0 (by /u/본인아이디) 를 넣어 주세요.")

SUBS = ["books", "suggestmeabook", "printSF", "Thrillers", "literature"]
THREADS_PER_QUERY = 5


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            time.sleep(7)
            return data
        except urllib.error.HTTPError as e:
            print(f"  ! HTTP {e.code} {url[:80]}")
            if e.code == 429:
                time.sleep(60)
                continue
            return None
    return None


def comments(node, out, depth=0):
    for c in node.get("data", {}).get("children", []):
        d = c.get("data", {})
        if c.get("kind") == "t1" and d.get("body"):
            out.append(dict(score=d.get("score", 0), depth=depth, body=d["body"]))
            if isinstance(d.get("replies"), dict):
                comments(d["replies"], out, depth + 1)


slug, queries = sys.argv[1], sys.argv[2:]
seen, threads = set(), []
for q in queries:
    url = ("https://www.reddit.com/r/" + "+".join(SUBS) + "/search.json?restrict_sr=1&sort=relevance&t=all&limit="
           + str(THREADS_PER_QUERY) + "&q=" + urllib.parse.quote(q))
    res = get(url)
    for p in (res or {}).get("data", {}).get("children", []):
        d = p["data"]
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        print(f"- r/{d['subreddit']} {d['num_comments']}댓글: {d['title'][:70]}")
        th = get("https://www.reddit.com" + d["permalink"] + ".json?limit=500&sort=top")
        cs = []
        if th and len(th) > 1:
            comments(th[1], cs)
        threads.append(dict(id=d["id"], subreddit=d["subreddit"], title=d["title"], url="https://www.reddit.com" + d["permalink"],
                            score=d.get("score"), num_comments=d.get("num_comments"), selftext=d.get("selftext", ""), comments=cs))

out = ROOT / "data" / "reddit" / f"{slug}.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(queries=queries, fetched=time.strftime("%Y-%m-%d"), threads=threads), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n저장: {out}  (스레드 {len(threads)}개, 댓글 {sum(len(t['comments']) for t in threads)}개)")
