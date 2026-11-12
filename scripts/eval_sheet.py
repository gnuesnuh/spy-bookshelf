"""기준 시트(Google 시트)를 정답지로 삼아 우리 로직을 검증한다.

검증 1. 번역본 매칭: 원제+저자만 주고(영미권 추천 소스가 주는 정보) YES24로 국내판을 찾게 한 뒤
        시트의 한국어 제목·번역 여부와 비교한다.
검증 2. 서점 입점: build_data.py 결과(data/books.json)의 자동 조회 값과 시트 값을 비교한다.

사용법: python scripts/eval_sheet.py [시작 끝]   → data/cache/eval_*.json, 콘솔 요약
"""
import difflib, json, re, sys, urllib.parse
import build_data as bd

ROOT = bd.ROOT
sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔(cp949)에서도 ✅ 출력
args = [a for a in sys.argv[1:] if a.isdigit()]
books = bd.load_sheet()
lo, hi = (int(args[0]), int(args[1])) if len(args) == 2 else (0, len(books))


import matching  # find_korean 등은 공용 모듈로 옮겼다

en, author_ok = matching.en, matching.author_ok


def find_korean(original, author):
    """(국내판 제목, 근거, 원제필드) — 기존 채점 코드와 같은 반환 형식."""
    item, how = matching.find_korean(original, author)
    how = "음역 일치 ⚠️" if how == "음역 일치" else how
    return (item["title"], how, item.get("originalTitle")) if item else (None, how, None)


rows = []
for b in books[lo:hi]:
    sheet_tr = "미번역" not in b["note"]
    title, how, ot = find_korean(b["original"], b["author"])
    sheet_t = bd.norm(re.sub(r"\(.*?\)", "", b["title"]))
    hit_t = bd.norm(title or "")
    alias = [bd.norm(a) for a in bd.ALIASES.get(b["title"], [])]
    same = bool(title) and (sheet_t[:4] in hit_t or hit_t[:4] in sheet_t or any(a[:4] in hit_t for a in alias))
    rows.append(dict(id=b["id"], sheet_title=b["title"], original=b["original"], author=b["author"],
                     sheet_translated=sheet_tr, found=title, how=how, found_original=ot, same_title=same))
    flag = ("✅" if same else "≠ ") if title else ("✅" if not sheet_tr else "❌")
    print(f"{flag} {b['title'][:18]:18} | 시트:{'번역' if sheet_tr else '미번역'} | 찾음:{title or '-'} ({how})", flush=True)

if (lo, hi) != (0, len(books)):
    prev = ROOT / "data" / "cache" / "eval_translation.part.json"
    old = json.loads(prev.read_text(encoding="utf-8")) if prev.exists() else []
    old = [r for r in old if r["id"] not in {x["id"] for x in rows}] + rows
    prev.write_text(json.dumps(old, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(0)
