"""질의별 추천 목록(data/queries/<slug>.json)에 국내판·서점 입점·평점을 붙여 결과 JSON, 웹앱 데이터, 시트(xlsx)를 만든다.

사용법:  python scripts/build_query.py why-fish            (목록 → 국내 정보 부착 → 웹앱·xlsx)
        python scripts/build_query.py why-fish --list     (목록만 먼저 웹앱에 올린다. 입점 칸은 '조회 중')
        python scripts/build_query.py why-fish --no-reviews  (리뷰 수집을 건너뛴다 — 요약을 합친 뒤 다시 돌릴 때)

결과는 단계별로 저장된다: 목록이 먼저 data/lists.js 에 올라가고, 책이 한 권 조회될 때마다 갱신된다.
웹앱은 조회가 덜 끝난 책을 '조회 중'으로 보여 준다. 국내 정보가 끝나면 독자 리뷰를 수집하고(3단계), 웹앱은
요약 전인 책을 '리뷰 N건 수집 · 요약 대기'로 보여 준다. 요약(모델)과 영상화(collect_adaptations.py)는 그다음에 채운다.

목록 파일의 책 한 줄: [카테고리, 한국어 제목(비워도 됨), 원제, 저자(한글), 수상·선정 이력, 추천 포인트, Goodreads 검색어, 비고]
또는 같은 이름의 키를 가진 사전({"category":…, "original":…, "author":…, "author_orig":…, "lang":"ja", …}).
"""
import json
import re
import sys
import threading
from datetime import date

sys.argv = [a for a in sys.argv if a != "--refresh"] + (["--refresh"] if "--refresh" in sys.argv else [])
import build_data as bd  # 밀리·리디·크레마·Goodreads·YES24 조회와 국내판 매칭을 그대로 쓴다
import build_site

ROOT = bd.ROOT
sys.stdout.reconfigure(encoding="utf-8")
slug = sys.argv[1]
list_only = "--list" in sys.argv
spec = json.loads((ROOT / "data" / "queries" / f"{slug}.json").read_text(encoding="utf-8"))
out_path = bd.list_path(slug)

books = []
for n, row in enumerate(spec["books"]):
    if isinstance(row, dict):   # 사전 형식: 추가 필드(lang, author_orig 등)를 그대로 넘긴다
        b = dict(row)
    else:
        cat, title, orig, author, awards, summary, grq, note = row
        b = dict(category=cat, title=title, original=orig, author=author, awards=awards, summary=summary,
                 grq=grq, note=note)
    b.update(id=f"{slug}-{n + 1}", list=spec["title"], original=b.get("original") or "-", grq=b.get("grq") or "",
             title=b.get("title") or "", note=b.get("note") or "", sheet={}, pending=True)
    # PLAYBOOK 5절: 카테고리의 '[1순위] 판단·확률' → tier=1, category='판단·확률' (웹앱이 순위를 따로 보여 준다)
    m = re.match(r"\s*\[(\d)순위\]\s*(.*)", b.get("category") or "")
    if m:
        b["tier"], b["category"] = int(m.group(1)), m.group(2).strip() or ("%s순위" % m.group(1))
    b["group"] = b["category"]
    books.append(b)
out = dict(slug=slug, query=spec["query"], title=spec["title"], subtitle=spec["subtitle"],
           updated=date.today().isoformat(), books=books)
_save = threading.Lock()


def save():
    with _save:
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        build_site.main()


# 1단계: 목록만 먼저 올린다 (이전 결과가 있으면 조회된 값을 그대로 이어 쓴다)
if out_path.exists():
    old = {b["id"]: b for b in json.loads(out_path.read_text(encoding="utf-8")).get("books", []) if "korean" in b}
    for b in books:
        o = old.get(b["id"])
        if o and o.get("original") == b["original"] and o.get("author") == b["author"]:
            b.update({k: o[k] for k in ("stores", "goodreads", "korean", "cover", "untranslated", "screen", "review", "reviewCount")
                      if k in o})
save()
if list_only:
    sys.exit(0)

# 2단계: 국내 정보 부착 — 여러 권을 동시에, 한 권 끝날 때마다 저장
def done(b):
    b.pop("pending", None)
    print(b["title"], {k: v["status"] for k, v in b["stores"].items()}, "| 국내판:", b["korean"]["verdict"], flush=True)
    save()


bd.enrich_all(books, done)
# 번역서가 아닌 원서만 있는 책은 '미번역 명작'으로 모은다(원래 갈래는 group 에 남는다). 국내서(원제 '-')는 제외
for b in books:
    if b["korean"]["verdict"] == "none" and b["original"] not in ("-", ""):
        b["category"] = "미번역 명작"
save()

# PLAYBOOK 5.1: 국내판 있는 책이 목표(기본 10권)에 못 미치면 다음 순위로 확장해야 한다
TARGET = int(sys.argv[sys.argv.index("--target") + 1]) if "--target" in sys.argv else 10
have = [b for b in books if b["korean"]["verdict"] in ("confirmed", "likely") and b["category"] != "기준 도서"]
ebook = [b for b in have if any(b["stores"][k]["status"] in ("yes", "select", "buy") for k in b["stores"])]
tiers = sorted({b.get("tier") for b in books if b.get("tier")})
by_tier = " · ".join("%d순위 %d/%d" % (t, sum(1 for b in have if b.get("tier") == t), sum(1 for b in books if b.get("tier") == t))
                     for t in tiers)
print("\n국내판 있는 책 %d권 (목표 %d권) · 그중 전자책·구독 가능 %d권 · 미번역 %d권%s" % (
    len(have), TARGET, len(ebook), sum(1 for b in books if b["category"] == "미번역 명작"),
    (" · 순위별 국내판 " + by_tier) if by_tier else ""), flush=True)
print("→ " + ("목표 충족: 확장하지 않는다." if len(have) >= TARGET else
              "목표 미달: PLAYBOOK 5.1대로 %s순위 후보를 추가한 뒤 다시 실행한다." % ((max(tiers) + 1) if tiers and max(tiers) < 4 else "다음")),
      flush=True)

# 3단계: 독자 리뷰 수집 — 끝나면 책마다 수집 건수를 붙여 다시 저장한다(요약은 그다음 단계)
if "--no-reviews" not in sys.argv:
    import subprocess
    print("독자 리뷰 수집 중… (Goodreads 는 권당 수 초)", flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "collect_reviews.py"), slug], check=False)
    for b in books:
        if "review" not in b:
            b["reviewCount"] = bd.review_count(b["id"])
    save()
    todo = [b["id"] for b in books if "review" not in b and (b.get("reviewCount") or 0) >= 3]
    if todo:
        print("요약 대기 %d권: Claude Code 가 data/reviews/<id>.json 을 읽고 요약해 merge_summaries.py 로 합친 뒤 "
              "build_query.py %s --no-reviews 를 다시 실행한다 → %s" % (len(todo), slug, " ".join(todo)), flush=True)

# ---- 시트(xlsx): 기존 Google 시트와 같은 배치 (보조 출력) ----
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

LBL = dict(
    yes24={"yes": "YES24 가능", "partial": "일부 가능", "no": "eBook 없음", "unknown": "확인 불가"},
    millie={"yes": "밀리의서재 가능", "no": "밀리 미입점", "unknown": "확인 불가"},
    ridi={"select": "리디셀렉트 가능", "buy": "리디 단권 가능", "no": "리디 미입점", "unknown": "확인 불가"},
    crema={"yes": "크레마 가능", "no": "크레마 미입점", "unknown": "확인 불가"})
MARK = {"confirmed": "국내판 확정 ✅", "likely": "국내판 유력 ⚠️", "none": "국내판 확인 안 됨", "unknown": "국내판 확인 불가 ❓"}
wb = Workbook()
ws = wb.active
ws.title = spec["query"][:28]
ws["B2"] = spec["title"]; ws["B2"].font = Font(bold=True, size=15)
ws["B3"] = spec["subtitle"]; ws["B3"].font = Font(color="666666")
n_ok = sum(1 for r in books if any(r["stores"][k]["status"] in ("yes", "select", "buy") for k in LBL))
n_trans = sum(1 for r in books if r["korean"]["verdict"] in ("confirmed", "likely"))
for c, v in zip("BEHK", ["총 추천 도서", "국내 출간 확인", "국내 eBook 구매·구독 가능", "기준일"]):
    ws[f"{c}5"] = v; ws[f"{c}5"].font = Font(bold=True, color="666666")
for c, v in zip("BEHK", [f"{len(books)}권", f"{n_trans}권", f"{n_ok}권", out["updated"]]):
    ws[f"{c}6"] = v; ws[f"{c}6"].font = Font(bold=True, size=13)
head = ["카테고리", "한국어 제목", "원제", "저자", "수상 및 선정 이력", "영미권/국내 평점", "리뷰 요약 및 추천 포인트",
        "YES24 eBook (단권 구매)", "밀리의서재", "리디셀렉트", "크레마클럽", "비고 (국내판)"]
thin = Side(style="thin", color="DDDDDD")
for j, h in enumerate(head):
    c = ws.cell(row=8, column=2 + j, value=h)
    c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="2F3B4C")
    c.alignment = Alignment(wrap_text=True, vertical="center")
for i, r in enumerate(books):
    s, gr, k = r["stores"], r["goodreads"], r["korean"]
    paper = s["yes24"].get("paper") or {}
    kr = s["yes24"].get("rating") or s["yes24"].get("bookRating") or s["crema"].get("rating")
    rating = " / ".join([f"Goodreads {gr['rating']:.2f} ({gr['count']:,})" if gr else "Goodreads -",
                         f"국내 {kr}" if kr else "국내 -"])
    note = [MARK[k["verdict"]]]
    if k.get("title"):
        note.append(" ".join(x for x in [k.get("publisher"), k.get("date")] if x) + (" · " + paper["status"] if paper else ""))
    review = (r.get("review") or {}).get("text") or r["summary"]
    vals = [r["category"], r["title"], r["original"], r["author"], r["awards"], rating, review,
            LBL["yes24"].get(s["yes24"]["status"]), LBL["millie"].get(s["millie"]["status"]),
            LBL["ridi"].get(s["ridi"]["status"]), LBL["crema"].get(s["crema"]["status"]),
            " · ".join(x for x in note + [r["note"]] if x)]
    links = [None, paper.get("url"), gr and gr.get("url"), None, None, None, None,
             s["yes24"].get("url"), s["millie"].get("url"), s["ridi"].get("url"), s["crema"].get("url"), None]
    for j, v in enumerate(vals):
        c = ws.cell(row=9 + i, column=2 + j, value=v)
        c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = Border(bottom=thin)
        if links[j]:
            c.hyperlink = links[j]; c.font = Font(color="1F5FAD", underline="single")
        if 7 <= j <= 10:
            ok = "가능" in (v or "")
            c.fill = PatternFill("solid", fgColor="E6F4EA" if ok else ("FFF4E0" if v == "확인 불가" else "F7F7F7"))
for col, w in zip("ABCDEFGHIJKLM", [2, 20, 26, 26, 16, 34, 24, 52, 14, 14, 14, 14, 26]):
    ws.column_dimensions[col].width = w
ws.freeze_panes = "D9"
ws.auto_filter.ref = f"B8:M{8 + len(books)}"
xp = ROOT / f"추천_{spec['query']}.xlsx"
try:
    wb.save(xp)
    print("saved", xp)
except PermissionError:
    print("xlsx 저장 실패: 파일이 엑셀에서 열려 있습니다 →", xp)
