"""책마다 영상화(영화·드라마) 작품을 찾아 data/adaptations.json 에 저장한다.

사용법:  python scripts/collect_adaptations.py [목록이름]   (캐시 사용. 목록이름 예: why-fish)
        python scripts/collect_adaptations.py --refresh  (다시 조회)

1) 위키데이터: Goodreads 작품 번호(P8383)로 책 항목을 찾고, 그 책을 원작(P144)으로 하는 영화·드라마를 조회한다.
   -> source "wikidata" (원작 관계가 명시된 확정 값)
2) TMDB(.env 의 TMDB_API_KEY): 위 결과의 한국어 제목·연도·포스터·국내 OTT 제공처를 채운다.
3) 위키데이터에 없던 책은 TMDB 에서 원제로 검색해, 제목이 같고 '소설 원작' 키워드가 붙은 작품만 받는다.
   -> source "tmdb" (추정 값. 화면에 '추정'으로 표시)
"""
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import CACHE, DATA, REFRESH, ROOT, UA, load_list, norm  # noqa: E402

OUT = DATA / "adaptations.json"
# 영화, TV 시리즈, 미니시리즈, TV 영화, TV 프로그램, 시즌, 애니메이션 시리즈
WD_TYPES = {"Q11424": "movie", "Q5398426": "tv", "Q1259759": "tv", "Q506240": "movie", "Q15416": "tv",
            "Q3464665": "tv", "Q117467246": "tv", "Q63952888": "tv"}
BASED_ON = {818, 246466, 9672}  # based on novel or book / based on memoir / based on true story(논픽션)


def env(name):
    f = ROOT / ".env"
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        if line.strip().startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"') or None
    return None


TMDB_KEY = env("TMDB_API_KEY")


def get_json(url, label, secret=""):
    """캐시된 JSON GET. 키는 캐시 이름과 오류 메시지에 남기지 않는다."""
    f = CACHE / hashlib.md5(url.encode()).hexdigest()
    if f.exists() and not REFRESH:
        return json.loads(f.read_bytes())
    try:
        raw = urllib.request.urlopen(urllib.request.Request(
            url + secret, headers={"User-Agent": "book-shelf-script/1.0", "Accept": "application/json"}),
            timeout=60).read()
    except urllib.error.HTTPError as e:
        print("  ! 조회 실패", label, e.code, file=sys.stderr)
        return None
    except Exception as e:
        print("  ! 조회 실패", label, type(e).__name__, file=sys.stderr)
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    f.write_bytes(raw)
    time.sleep(0.3)
    return json.loads(raw)


def tmdb(path, **params):
    if not TMDB_KEY:
        return None
    q = urllib.parse.urlencode(dict(params, language="ko-KR"))
    return get_json("https://api.themoviedb.org/3/%s?%s" % (path, q), "TMDB " + path, "&api_key=" + TMDB_KEY)


def wikidata(work_ids):
    vals = " ".join('"%s"' % w for w in work_ids)
    sparql = """SELECT ?gr ?ad ?adLabel ?type ?year ?mid ?tid ?stid WHERE {
      VALUES ?gr { %s }
      ?book wdt:P8383 ?gr .
      ?ad wdt:P144 ?book ; wdt:P31 ?type .
      OPTIONAL { ?ad wdt:P577 ?d . BIND(YEAR(?d) AS ?year) }
      OPTIONAL { ?ad wdt:P4947 ?mid }
      OPTIONAL { ?ad wdt:P4983 ?tid }
      OPTIONAL { ?ad wdt:P179 ?series . ?series wdt:P4983 ?stid }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "ko,en". }
    }""" % vals
    d = get_json("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(sparql), "Wikidata")
    return None if d is None else d["results"]["bindings"]


def tmdb_fill(kind, tid):
    """TMDB 상세 -> 화면용 정보. 실패하면 None."""
    d = tmdb("%s/%s" % (kind, tid), append_to_response="watch/providers,keywords,credits,aggregate_credits")
    if not d:
        return None
    kr = ((d.get("watch/providers") or {}).get("results") or {}).get("KR") or {}
    date = d.get("release_date") or d.get("first_air_date") or ""
    kw = d.get("keywords") or {}
    return dict(kind=kind, title=d.get("title") or d.get("name") or "",
                original=d.get("original_title") or d.get("original_name") or "",
                year=int(date[:4]) if date[:4].isdigit() else None,
                poster=("https://image.tmdb.org/t/p/w185" + d["poster_path"]) if d.get("poster_path") else "",
                url="https://www.themoviedb.org/%s/%s" % (kind, tid),
                watch=[p["provider_name"] for p in kr.get("flatrate") or []],
                keywords=[k["id"] for k in (kw.get("keywords") or kw.get("results") or [])],
                votes=d.get("vote_count") or 0,
                crew=[c.get("name") or "" for c in ((d.get("credits") or {}).get("crew") or [])
                      + ((d.get("aggregate_credits") or {}).get("crew") or []) + (d.get("created_by") or [])])


def from_wikidata(rows, by_work):
    out = {}
    for r in rows:
        kind = WD_TYPES.get(r["type"]["value"].rsplit("/", 1)[-1])
        if not kind:
            continue
        v = lambda k: r[k]["value"] if k in r else None
        tid = v("mid") if kind == "movie" else (v("tid") or v("stid"))
        key = (kind, tid) if tid else ("wd", v("ad"))
        item = out.setdefault(by_work[v("gr")], {}).setdefault(key, dict(
            kind=kind, title=v("adLabel"), original="", year=int(v("year")) if v("year") else None,
            poster="", url=v("ad"), watch=[], source="wikidata", tmdb=tid))
        if v("year") and (item["year"] is None or int(v("year")) < item["year"]):
            item["year"] = int(v("year"))
    return {bid: list(items.values()) for bid, items in out.items()}


def from_tmdb_search(book):
    """위키데이터에 없을 때: 원제와 제목이 같고 '원작 있음' 키워드가 붙은 작품만."""
    q = re.sub(r"\(.*?\)", "", book["original"].split("/")[0])
    q = re.sub(r"\b(Series|Trilogy)\b", "", q).strip()
    found, failed = [], False
    for kind in ("movie", "tv"):
        res = tmdb("search/" + kind, query=q)
        if res is None:
            failed = True
            continue
        for hit in res.get("results", [])[:5]:
            names = [hit.get("title"), hit.get("name"), hit.get("original_title"), hit.get("original_name")]
            if not any(n and norm(n) == norm(q) for n in names):
                continue
            info = tmdb_fill(kind, hit["id"])
            # 같은 제목의 다른 작품을 막기 위해 제작진(원작 크레딧)에 책 저자가 있어야 한다
            surname = norm(book["goodreads"]["author"].split()[-1])
            if info and BASED_ON & set(info["keywords"]) and any(surname and surname in norm(c) for c in info["crew"]):
                found.append(dict(info, source="tmdb", tmdb=str(hit["id"])))
    return found, failed


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    slug = ([a for a in sys.argv[1:] if not a.startswith("--")][:1] or [None])[0]          # 목록 이름(예: why-fish). 없으면 기준 시트
    books = [b for b in load_list(slug)["books"] if b.get("stores")]
    by_work = {b["goodreads"]["work"]: b["id"] for b in books if (b.get("goodreads") or {}).get("work")}
    rows = wikidata(sorted(by_work))
    wd = from_wikidata(rows, by_work) if rows is not None else {}
    result = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}   # 다른 목록의 결과는 유지
    for b in books:
        items, status = wd.get(b["id"], []), "ok"
        if rows is None:
            status = "unknown"
        for it in items:  # TMDB 로 한국어 제목·포스터·OTT 보강
            info = it["tmdb"] and tmdb_fill(it["kind"], it["tmdb"])
            if info:
                it.update({k: info[k] for k in ("title", "original", "poster", "url", "watch")},
                          year=info["year"] or it["year"])
        if not items and b.get("goodreads"):
            items, failed = from_tmdb_search(b)
            if failed and not items:
                status = "unknown"
        seen, uniq = set(), []
        for it in sorted(items, key=lambda x: (x["year"] or 9999)):
            k = (it["kind"], norm(it["title"]), it["year"])
            if k not in seen:
                seen.add(k)
                uniq.append({k2: it[k2] for k2 in ("kind", "title", "original", "year", "poster", "url", "watch", "source")})
        result[b["id"]] = dict(status=status, items=uniq)
        if uniq:
            print(b["title"], "→", " / ".join("%s(%s %s%s)%s" % (
                i["title"], "영화" if i["kind"] == "movie" else "드라마", i["year"] or "?",
                "" if i["source"] == "wikidata" else " 추정", (" @" + ",".join(i["watch"])) if i["watch"] else "")
                for i in uniq))
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    mine = [result[b["id"]] for b in books]
    print("영상화 확인 %d권 / %d권, 확인 불가 %d권" % (sum(1 for v in mine if v["items"]), len(mine),
                                             sum(1 for v in mine if v["status"] == "unknown")))


if __name__ == "__main__":
    main()
