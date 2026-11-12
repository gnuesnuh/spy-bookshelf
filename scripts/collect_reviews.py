"""data/books.json 의 각 책에 대해 실제 독자 리뷰를 수집해 data/reviews/<id>.json 에 저장한다.

사용법:  python scripts/collect_reviews.py            (캐시 사용)
        python scripts/collect_reviews.py --refresh  (다시 수집)

수집처 (COLLECTORS 에 함수를 추가하면 수집처가 늘어난다)
  goodreads  책 페이지에 포함된 리뷰 (해외, 최대 30개)
  ridi       리디 책 페이지에 포함된 구매자 리뷰 (국내, 최대 10개)
  yes24      크레마클럽 리뷰 목록 (국내, 크레마클럽 도서만)

리뷰 원문은 요약 입력으로만 쓰며 화면에는 노출하지 않는다.
"""
import html
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import DATA, fetch  # noqa: E402

OUT = DATA / "reviews"
MAX_CHARS = 700   # 리뷰 1개당 보관 길이
MAX_PER_SOURCE = 15


def clean(text):
    text = re.sub(r"<br\s*/?>|</p>", "\n", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()[:MAX_CHARS]


def keep(rows):
    rows = [r for r in rows if len(r["text"]) >= 20]
    rows.sort(key=lambda r: -(r.get("likes") or 0))
    return rows[:MAX_PER_SOURCE]


def goodreads(book):
    g = book.get("goodreads")
    if not g:
        return []
    m = None
    for _ in range(4):  # Goodreads는 연속 요청 시 빈 페이지를 주기도 해서 천천히 재시도한다
        raw = fetch(g["url"])
        m = raw and re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw, re.S)
        if m:
            break
        time.sleep(6)
    if not m:
        return []
    time.sleep(1.5)
    state = json.loads(m.group(1))["props"]["pageProps"]["apolloState"]
    return keep([dict(rating=v.get("rating"), likes=v.get("likeCount") or 0, text=clean(v.get("text")))
                 for k, v in state.items() if k.startswith("Review:")])


def ridi(book):
    s = book["stores"]["ridi"]
    if s["status"] == "no" or "/books/" not in s["url"]:
        return []
    raw = fetch(s["url"])
    m = raw and re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', raw, re.S)
    if not m:
        return []
    found = []

    def walk(o):  # 리뷰 셀 위치가 페이지마다 달라서 구조를 훑어 찾는다
        if isinstance(o, dict):
            cell = o.get("cell__BookDetailHomeReview")
            if isinstance(cell, dict):
                found.extend(cell.get("reviews") or [])
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(json.loads(m.group(1)))
    return keep([dict(rating=r.get("rating"), likes=r.get("likeVoteCnt") or 0,
                      text=clean(r.get("content") or r.get("contents") or r.get("review") or ""))
                 for r in found])


def yes24(book):
    s = book["stores"]["crema"]
    if s["status"] != "yes":
        return []
    goods = s["url"].rsplit("/", 1)[-1]
    raw = fetch("https://cremaclub.yes24.com/Bookclub/BookClubGoodsReviewList?goodsNo=%s&pageNo=1&sortGb=2"
                "&checkDojung=&isFirstLoad=1" % goods)
    rows = []
    for part in (raw or "").split('class="reviewInfoGrp')[1:]:
        r = re.search(r"평점(\d+)점", part)
        c = re.search(r'reviewInfoBot crop.*?<div class="review_cont">(.*?)<span class="review_more"', part, re.S) \
            or re.search(r'<div class="review_cont">(.*?)</div>', part, re.S)
        if c:
            rows.append(dict(rating=int(r.group(1)) / 2 if r else None, likes=0, text=clean(c.group(1))))
    return keep(rows)


COLLECTORS = {"goodreads": goodreads, "ridi": ridi, "yes24": yes24}
REGION = {"goodreads": "overseas", "ridi": "domestic", "yes24": "domestic"}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    books = json.loads((DATA / "books.json").read_text(encoding="utf-8"))["books"]
    total = {k: 0 for k in COLLECTORS}
    for b in books:
        got = {}
        for name, fn in COLLECTORS.items():
            try:
                got[name] = fn(b)
            except Exception as e:  # 한 수집처 실패가 전체를 막지 않게 한다
                print("  !", b["title"], name, e, file=sys.stderr)
                got[name] = []
            total[name] += len(got[name])
        (OUT / (b["id"] + ".json")).write_text(json.dumps(
            dict(id=b["id"], title=b["title"], original=b["original"], author=b["author"], reviews=got),
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(b["title"], {k: len(v) for k, v in got.items()})
    print("합계", total)


if __name__ == "__main__":
    main()
