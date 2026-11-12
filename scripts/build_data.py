"""시트를 내려받아 서점별 입점 여부와 평점을 조회하고 data/books.json 을 만든다.

사용법:  python scripts/build_data.py            (캐시 사용)
        python scripts/build_data.py --refresh  (서점에 다시 조회)

조회 경로
  밀리의서재  live-api.millie.co.kr 검색 API
  리디        search-api.ridibooks.com 검색 API (is_select = 리디셀렉트)
  크레마클럽  cremaclub.yes24.com 검색 페이지 (YES24 평점·리뷰 수 포함)
  Goodreads   book/auto_complete (평점·평가 수)
  YES24 eBook 자동 조회가 막혀 있어 시트 값을 그대로 쓴다 (source: sheet)
"""
import hashlib
import html
import io
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
SHEET_ID = "10hYwTqAXoqn-qZ3u1YCN4RVWBhYQGTcBXctbljjc9mQ"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
REFRESH = "--refresh" in sys.argv

# 시트 제목이 실제 국내 출간명과 다른 책: 시트 제목 -> 서점 검색어 목록
GR_PICK = json.loads((ROOT / "scripts" / "goodreads_pick.json").read_text(encoding="utf-8"))
_sum = DATA / "summaries.json"   # scripts/summarize_reviews.py 가 수집 리뷰로 만든 요약
REVIEWS = json.loads(_sum.read_text(encoding="utf-8")) if _sum.exists() else {}


_scr = DATA / "adaptations.json"
SCREEN = json.loads(_scr.read_text(encoding="utf-8")) if _scr.exists() else {}


def _yes24_key():
    """YES24 Open API 키: 환경변수 YES24_API_KEY 또는 프로젝트 루트의 .env 파일."""
    import os
    key = os.environ.get("YES24_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("YES24_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key or None


YES24_KEY = _yes24_key()
ALIASES = json.loads((ROOT / "scripts" / "aliases.json").read_text(encoding="utf-8"))


_locks, _last = {}, {}
_guard = threading.Lock()
GAP = {"www.goodreads.com": 1.5, "apis.yes24.com": 0.25}   # 호스트별 최소 요청 간격(초), 기본 0.6


def _throttle(url):
    """같은 호스트에는 한 번에 한 요청, 최소 간격을 지킨다. 다른 호스트끼리는 동시에 나간다."""
    host = urllib.parse.urlsplit(url).netloc
    with _guard:
        lock = _locks.setdefault(host, threading.Lock())
    with lock:
        wait = _last.get(host, 0) + GAP.get(host, 0.6) - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()


def fetch(url, binary=False, headers=None):
    key = hashlib.md5(url.encode()).hexdigest()
    f = CACHE / key
    if f.exists() and not REFRESH:
        raw = f.read_bytes()
    else:
        _throttle(url)
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        try:
            raw = urllib.request.urlopen(req, timeout=20).read()
        except urllib.error.HTTPError as e:
            body = e.read()
            if e.code == 404 and (b"SEARCH_001" in body or b"GOODS_001" in body):  # YES24 API: 결과 없음
                raw = body
            else:
                print("  ! fetch failed", url[:70], e, file=sys.stderr)
                return None
        except Exception as e:  # 조회 실패는 '확인 불가'로 남긴다
            print("  ! fetch failed", url[:70], e, file=sys.stderr)
            return None
        if not raw:  # 빈 응답(과다 요청 차단)은 캐시하지 않는다
            print("  ! empty response", url[:70], file=sys.stderr)
            time.sleep(3)
            return None
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_bytes(raw)
    return raw if binary else raw.decode("utf-8", errors="replace")


sys.path.insert(0, str(Path(__file__).resolve().parent))
import matching  # noqa: E402  (원제+저자 → 국내판 찾기, 공용 모듈)

matching.configure(fetch, YES24_KEY)


def norm(s):
    return re.sub(r"[^0-9a-z가-힣]", "", (s or "").lower())


def queries(title):
    """시트 제목 -> 검색어 후보."""
    if title in ALIASES:
        return ALIASES[title]
    out = []
    for part in title.split("/"):
        part = re.sub(r"\(.*?\)", "", part)
        part = re.sub(r"(시리즈|3부작)", "", part).strip()
        if part:
            out.append(part)
    return out


def author_key(author):
    return norm(author.split()[-1])


def is_match(q, author, r_title, r_author):
    nq, nt = norm(q), norm(r_title)
    if not nq or nq not in nt:
        return False
    # 저자 표기가 서점마다 달라서(헤론/헤런) 성 앞 두 글자만 비교
    ak = author_key(author)
    if ak[:2] in norm(r_author):
        return True
    return nq == nt and ak[:1] in norm(r_author)


def millie(q):
    raw = fetch("https://live-api.millie.co.kr/v2/search/content?searchType=content&contentCode=0&startPage=1&keyword="
                + urllib.parse.quote(q))
    if raw is None:
        return None
    return [dict(title=b["content_name"], author=b["author"], ok=bool(b.get("is_service")),
                 url="https://www.millie.co.kr/v3/search/result/" + urllib.parse.quote(b["content_name"]),
                 reviews=int(b.get("content_review_count") or 0),
                 cover=(b.get("content_thumb_url") or "").replace("/200x/", "/400x/"), ebook=b.get("content_code") == "245")
            for b in json.loads(raw)["RESP_DATA"]["list"]]


def ridi(q):
    raw = fetch("https://search-api.ridibooks.com/search?where=book&site=ridi-store&what=base&start=0&keyword="
                + urllib.parse.quote(q))
    if raw is None:
        return None
    return [dict(title=b["title"], author=b["author"], select=bool(b.get("is_select")),
                 url="https://ridibooks.com/books/" + b["b_id"],
                 cover="https://img.ridicdn.net/cover/" + b["b_id"] + "/xlarge",
                 rating=b.get("buyer_rating_score"), count=b.get("buyer_rating_count"))
            for b in json.loads(raw)["books"]]


def crema(q):
    raw = fetch("https://cremaclub.yes24.com/BookClub/Search?query=" + urllib.parse.quote(q))
    if raw is None:
        return None
    i = raw.find('id="yesSchList"')
    out = []
    if i < 0:
        return out
    for li in raw[i:].split('<div class="itemUnit">')[1:]:
        m = re.search(r'class="gd_name" href="/BookClub/Detail/(\d+)">(.*?)</a>', li, re.S)
        if not m:
            continue
        a = re.search(r'info_auth">(.*?)</span>', li, re.S)
        r = re.search(r'class="yes_b">([\d.]+)<', li)
        c = re.search(r'txC_blue">([\d,]+)<', li)
        out.append(dict(title=html.unescape(m.group(2)).strip(),
                        author=re.sub(r"<.*?>|\s+", " ", html.unescape(a.group(1))).strip() if a else "",
                        goods=m.group(1), cover="https://image.yes24.com/goods/" + m.group(1) + "/L", url="https://cremaclub.yes24.com/BookClub/Detail/" + m.group(1),
                        rating=float(r.group(1)) if r else None,
                        reviews=int(c.group(1).replace(",", "")) if c else 0))
    return out


def goodreads(orig, override=None):
    q = re.sub(r"\(.*?\)", "", orig.split("/")[0])
    q = re.sub(r"\b(Series|Trilogy)\b", "", q).strip()
    q = override or q
    raw = fetch("https://www.goodreads.com/book/auto_complete?format=json&q=" + urllib.parse.quote(q))
    if raw is None:
        return None
    try:
        rows = json.loads(raw)
    except ValueError:
        return None
    return [dict(title=b["bookTitleBare"], author=b["author"]["name"], rating=float(b["avgRating"]),
                 count=b["ratingsCount"], work=str(b.get("workId") or ""),
                 cover="" if "nophoto" in b.get("imageUrl", "") else re.sub(r"\._S[XY]\d+_", "._SX240_", b.get("imageUrl", "")),
                 url="https://www.goodreads.com" + b["bookUrl"].split("?")[0])
            for b in rows[:5]]


def yes24(q, category="EBOOK"):
    """YES24 Open API(developers.yes24.com) eBook 검색. 키가 없으면 None."""
    if not YES24_KEY:
        return None
    raw = fetch("https://apis.yes24.com/v1/goods/itemList?category=" + category + "&detail=Y&pageSize=20&query="
                + urllib.parse.quote(q), headers={"X-Api-Key": YES24_KEY})
    if raw is None:
        return None
    try:
        items = (json.loads(raw).get("data") or {}).get("items") or []
    except ValueError:
        return None
    items = [i for i in items if not re.search("영어 ?원서|영문판|영어 ?소설|영어로 읽는", i.get("title") or "")]
    return [dict(title=i.get("title") or "", author=i.get("author") or "", status=i.get("itemStatus") or "",
                 url=i.get("link") or "", rating=i.get("starScore"), cover=i.get("cover") or "",
                 original=i.get("originalTitle") or "", ebook_id=i.get("ebookId"))
            for i in items]


def first(rows, pred):
    for r in rows:
        if pred(r):
            return r
    return None


_gold = DATA / "gold.json"   # 검수 정답지: 자동 매칭이 놓친 국내판의 수동 판정
GOLD = {g["id"]: g for g in json.loads(_gold.read_text(encoding="utf-8"))} if _gold.exists() else {}


def find_korean_edition(book):
    """원제+저자로 YES24 국내판을 찾는다 → (상품 dict 또는 None, 근거)."""
    if not YES24_KEY or not book.get("original") or book["original"] == "-":
        return None, "확인 불가"
    return matching.find_korean(book["original"], book["author"])


def check(book):
    qs = queries(book["title"]) if book.get("title") else []
    stores = {}
    cand = {}
    # 국내판을 먼저 확정하고, 그 제목을 서점 검색어 맨 앞에 둔다(시트 제목이 틀린 책 대비)
    kr_item, kr_how = find_korean_edition(book)
    if kr_item:
        kt = matching.base_title(kr_item["title"])
        qs = [kt] + [q for q in qs if norm(q) != norm(kt)]
    gold = GOLD.get(book.get("id") or "", {})
    gold_title = None
    if not kr_item and gold.get("verdict") in ("verified", "verified_alias") and gold.get("korean_title"):
        gold_title = gold["korean_title"]          # 자동으로 못 찾았지만 검수에서 확인된 국내 제목
        kt = matching.base_title(gold_title)
        qs = [kt] + [q for q in qs if norm(q) != norm(kt)]
        kr_how = "수동 검수"
    if not qs:  # 한국어 제목도 국내판도 없는 책(미번역 후보): 원제로만 검색해 '없음'을 확인한다
        qs = [re.sub(r"\(.*?\)", "", book.get("original") or "").strip() or "-"]
    cand["korean"] = dict(how=kr_how, title=(kr_item and kr_item.get("title")) or gold_title,
                          original=kr_item and kr_item.get("originalTitle"),
                          publisher=kr_item and kr_item.get("publisher"),
                          date=kr_item and str(kr_item.get("publishDate") or "")[:4])

    # 밀리의서재
    hit, failed, seen = None, False, []
    for q in qs:
        rows = millie(q)
        if rows is None:
            failed = True
            continue
        seen += rows
        hit = hit or first(rows, lambda r: r["ok"] and r["ebook"] and is_match(q, book["author"], r["title"], r["author"]))
    cand["millie"] = seen
    covers = {}
    if hit:
        covers["millie"] = hit["cover"]
    stores["millie"] = (dict(status="yes", url=hit["url"], matched=hit["title"], reviews=hit["reviews"]) if hit
                        else dict(status="unknown" if failed else "no"))

    # 리디
    hit, failed, seen = None, False, []
    for q in qs:
        rows = ridi(q)
        if rows is None:
            failed = True
            continue
        seen += rows
        ms = [r for r in rows if is_match(q, book["author"], r["title"], r["author"])]
        hit = hit or first(ms, lambda r: r["select"]) or first(ms, lambda r: True)
    cand["ridi"] = seen
    if hit:
        covers["ridi"] = hit["cover"]
        stores["ridi"] = dict(status="select" if hit["select"] else "buy", url=hit["url"], matched=hit["title"],
                              rating=hit["rating"], count=hit["count"])
    else:
        stores["ridi"] = dict(status="unknown" if failed else "no")

    # 크레마클럽
    hit, failed, seen = None, False, []
    for q in qs:
        rows = crema(q)
        if rows is None:
            failed = True
            continue
        seen += rows
        hit = hit or first(rows, lambda r: is_match(q, book["author"], r["title"], r["author"]))
    cand["crema"] = seen
    if hit:
        covers["crema"] = hit["cover"]
    stores["crema"] = (dict(status="yes", url=hit["url"], matched=hit["title"], rating=hit["rating"],
                            reviews=hit["reviews"]) if hit else dict(status="unknown" if failed else "no"))

    # YES24 eBook: 시트 값
    s = (book.get("sheet") or {}).get("yes24", "")
    st = "yes" if "YES24 가능" in s else "partial" if "일부" in s else "no"
    if stores["crema"]["status"] == "yes":
        st = "yes"  # 크레마클럽 도서는 YES24 eBook 상품이다
    stores["yes24"] = dict(status=st, source="crema" if stores["crema"]["status"] == "yes" else "sheet", note=s,
                           url="https://www.yes24.com/Product/Search?domain=EBOOK&query=" + urllib.parse.quote(qs[0]))
    if stores["crema"]["status"] == "yes":
        stores["yes24"]["url"] = stores["crema"]["url"].replace(
            "https://cremaclub.yes24.com/BookClub/Detail/", "https://www.yes24.com/Product/Goods/")
    # YES24 Open API 키가 있으면 시트 값 대신 실제 검색 결과로 덮어쓴다
    hit, failed, seen = None, False, []
    # 국내 제목이 시트와 다른 책을 잡기 위해 원제로도 검색하고, 원제(originalTitle)가 같은 한국어판을 인정한다
    orig = re.sub(r"\(.*?\)", "", (book.get("original") or "").split("/")[0]).strip().strip("-")
    for q in [x for x in qs + [orig] if x] if YES24_KEY else []:
        rows = yes24(q)
        if rows is None:
            failed = True
            continue
        seen += rows
        ms = [r for r in rows if is_match(q, book["author"], r["title"], r["author"])
              or (re.search("[가-힣]", r["title"]) and norm(orig) and norm(orig) in norm(r["original"])
                  and author_key(book["author"])[:2] in norm(r["author"]))]
        ms.sort(key=lambda r: -(r["rating"] or 0))
        hit = hit or first(ms, lambda r: "판매중" in r["status"]) or first(ms, lambda r: True)
    cand["yes24"] = seen
    if YES24_KEY and not failed:
        if hit:
            covers["yes24"] = hit["cover"]
            stores["yes24"] = dict(status="yes" if "판매중" in hit["status"] else "no", source="api", note=hit["status"],
                                   url=hit["url"], matched=hit["title"], rating=hit["rating"])
        else:
            stores["yes24"].update(status="no", source="api", note="검색 결과 없음")
    stores["yes24"]["sheet"] = s

    # YES24 종이책: 전자책이 없어도 종이책(판매중/절판)이 있는지 알려준다
    paper = None
    for q in [x for x in qs + [orig] if x] if YES24_KEY and not kr_item else []:
        rows = yes24(q, "BOOK") or []
        ms = [r for r in rows if is_match(q, book["author"], r["title"], r["author"])
              or (re.search("[가-힣]", r["title"]) and norm(orig) and norm(orig) in norm(r["original"])
                  and author_key(book["author"])[:2] in norm(r["author"]))]
        ms.sort(key=lambda r: (0 if "판매중" in r["status"] else 1, r["title"]))
        paper = paper or first(ms, lambda r: True)
    if kr_item:
        paper = dict(status=kr_item.get("itemStatus") or "", url=kr_item.get("link") or "",
                     title=kr_item.get("title") or "", cover=kr_item.get("cover") or "")
        # EBOOK 검색이 놓친 전자책: 종이책에 연결된 eBook 상품이 실제로 판매 중인지 확인한다
        if stores["yes24"]["status"] != "yes" and kr_item.get("ebookId"):
            det = matching.item_detail(kr_item["ebookId"])
            if det and "판매중" in (det.get("itemStatus") or ""):
                stores["yes24"].update(status="yes", source="api", note="종이책에 연결된 eBook",
                                       url=det.get("link") or kr_item.get("eBookLink"),
                                       matched=det.get("title"), rating=det.get("starScore"))
            elif det == {}:
                stores["yes24"]["note"] = "연결된 eBook은 절판·판매 종료"
        if not stores["yes24"].get("rating") and kr_item.get("starScore"):
            stores["yes24"]["bookRating"] = kr_item["starScore"]
    if paper:
        stores["yes24"]["paper"] = dict(status=paper["status"], url=paper["url"], matched=paper["title"])
        covers.setdefault("paper", paper["cover"])
    for k in ("millie", "ridi", "crema"):
        stores[k]["source"] = "auto"
        stores[k]["sheet"] = (book.get("sheet") or {}).get(k, "")
    stores["millie"].setdefault("url", "https://www.millie.co.kr/v3/search/result/" + urllib.parse.quote(qs[0]))
    stores["ridi"].setdefault("url", "https://ridibooks.com/search?q=" + urllib.parse.quote(qs[0]))
    stores["crema"].setdefault("url", "https://cremaclub.yes24.com/BookClub/Search?query=" + urllib.parse.quote(qs[0]))

    has_orig = book.get("original") and book["original"] != "-"
    gr = (goodreads(book["original"], book.get("grq") or GR_PICK.get(book.get("title"), {}).get("q")) or []) if has_orig else []
    cand["goodreads"] = gr
    cand["covers"] = covers
    return stores, cand


def load_sheet():
    raw = fetch(f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx", binary=True)
    if raw is None:
        raw = (DATA / "sheet.xlsx").read_bytes()
    else:
        (DATA / "sheet.xlsx").write_bytes(raw)
    wb = openpyxl.load_workbook(io.BytesIO(raw))
    books = []
    for n, ws in enumerate(wb):
        rows = list(ws.iter_rows(min_row=8, values_only=True))
        head = [str(c or "") for c in rows[0]]
        col = lambda *keys: next(i for i, h in enumerate(head) if any(k in h for k in keys))
        ci = dict(cat=col("구분", "카테고리"), title=col("한국어 제목"), original=col("원제"), author=col("저자"),
                  awards=col("선정 이력"), summary=col("요약"), yes24=col("YES24"), millie=col("밀리"),
                  ridi=col("리디"), crema=col("크레마"), note=col("비고"))
        rating_col = next((i for i, h in enumerate(head) if "평점" in h), None)
        for r in rows[1:]:
            if not r[ci["title"]]:
                continue
            g = lambda k: str(r[ci[k]] or "").strip()
            books.append(dict(
                id=f"{n + 1}-{len(books) + 1}", list=ws.title if n else "스파이 소설 & 논픽션",
                category=g("cat"), title=g("title"), original=g("original"), author=g("author"),
                awards=g("awards"), summary=g("summary"), note=g("note"),
                sheetRating=str(r[rating_col] or "") if rating_col is not None else "",
                sheet=dict(yes24=g("yes24"), millie=g("millie"), ridi=g("ridi"), crema=g("crema"))))
    return books


def enrich(b):
    """책 한 권에 서점 입점·국내판·평점·표지·영상화·리뷰 요약을 붙인다. 채점용 후보 기록을 돌려준다."""
    stores, cand = check(b)
    b["stores"] = stores
    gr = cand["goodreads"]
    pick = GR_PICK.get(b.get("title"), {}).get("i", 0)
    b["goodreads"] = gr[pick] if pick is not None and len(gr) > pick else None
    k = cand.pop("korean")
    in_store = bool(stores["yes24"]["status"] == "yes" or stores["yes24"].get("paper")
                    or any(stores[x]["status"] not in ("no", "unknown") for x in ("millie", "ridi", "crema")))
    # 국내판 판정: confirmed(원제 일치) / likely(음역·수동 검수·서점 제목 일치) / none(못 찾음) / unknown(조회 실패)
    verdict = ("confirmed" if k["how"] == "원제 일치" else "likely" if k["how"] in ("음역 일치", "수동 검수") or in_store
               else "unknown" if k["how"] == "확인 불가" else "none")
    how = k["how"] if k["title"] else ("서점 제목 일치" if in_store else k["how"])
    if not k["title"] and stores["yes24"].get("paper"):   # 원제 대조는 못 했지만 제목+저자로 찾은 종이책
        k["title"] = stores["yes24"]["paper"]["matched"]
    b["korean"] = dict(k, verdict=verdict, how=how)
    if not b.get("title"):  # 질의 목록에 한국어 제목을 안 적은 책은 찾은 국내 제목(없으면 원제)을 쓴다
        b["title"] = matching.base_title(k["title"]) if k["title"] else b["original"]
    b["untranslated"] = verdict == "none"
    cv = cand.pop("covers")
    # 국내판 표지 우선, 없으면 Goodreads 원서 표지
    b["cover"] = (cv.get("ridi") or cv.get("crema") or cv.get("yes24") or cv.get("paper") or cv.get("millie")
                  or (b["goodreads"] or {}).get("cover") or "")
    if b["id"] in SCREEN:   # scripts/collect_adaptations.py 결과
        b["screen"] = SCREEN[b["id"]]
    if b["id"] in REVIEWS:  # scripts/summarize_reviews.py 결과
        b["review"] = REVIEWS[b["id"]]
    return dict(title=b["title"], author=b["author"], original=b["original"], cand=cand,
                result={k2: v["status"] + ("|" + v.get("matched", "") if v.get("matched") else "")
                        for k2, v in stores.items()})


def enrich_all(books, on_done=None, workers=6):
    """여러 권을 동시에 조회한다. 한 권이 끝날 때마다 on_done(book) 을 부른다(진행 상황 저장용)."""
    reports = [None] * len(books)

    def work(i):
        reports[i] = enrich(books[i])
        if on_done:
            on_done(books[i])

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, range(len(books))))
    return reports


def list_path(slug):
    """목록 이름 → 결과 파일. 'spy'(기본)는 기준 시트, 그 밖은 data/queries/<slug>.result.json."""
    return DATA / "books.json" if slug in (None, "", "spy") else DATA / "queries" / (slug + ".result.json")


def load_list(slug=None):
    return json.loads(list_path(slug).read_text(encoding="utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    books = load_sheet()
    report = enrich_all(books, lambda b: print(b["title"], "→", {k: v["status"] for k, v in b["stores"].items()}))
    out = dict(slug="spy", query="스파이 소설·스릴러", title="스파이 소설 & 논픽션 명작 + 확장 장르 추천",
               subtitle="기준 시트(레딧 r/books 추천, CWA 대거상, 텔레그래프 역대 최고 20 등)의 65권",
               updated=date.today().isoformat(), books=books)
    (DATA / "books.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (CACHE / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    import build_site
    build_site.main()


if __name__ == "__main__":
    main()
