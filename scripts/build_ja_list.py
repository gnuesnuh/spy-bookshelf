"""일본 어워드·랭킹(소스 캐시)을 집계해 추천 목록 data/queries/<slug>.json 을 만든다. 모델 호출 없음.

사용법:  python scripts/build_ja_list.py <slug> [시작연도 끝연도] [--top 30] [--sources konomys,bunshun,honya]
   예:   python scripts/build_ja_list.py ja-mystery 2016 2026 --top 30 --sources konomys,bunshun
   먼저 python scripts/sources_ja.py 로 소스 캐시를 만들어 둔다.

점수: 소스·연도마다 (11 - 순위)점을 더한다. 여러 랭킹에 겹쳐 오른 작품이 위로 온다.
출력
  data/queries/<slug>.json             build_query.py 가 읽는 목록 (국내 제목·저자는 YES24 에서 찾은 값)
  data/queries/<slug>.unresolved.json  국내판을 자동으로 못 찾은 책 + 같은 저자의 '원제 미표기' 국내 출간작 후보
                                       → Claude Code 가 보고 scripts/ja_titles.json 에 판정을 적은 뒤 다시 실행
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
args = [a for a in sys.argv[1:] if a != "--refresh"]
import build_data as bd  # noqa: E402
import matching  # noqa: E402
import sources_ja  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def opt(name, default):
    return args[args.index(name) + 1] if name in args else default


slug = args[0]
years = [int(a) for a in args[1:] if a.isdigit() and len(a) == 4]
lo, hi = (years + [1900, 2100])[:2] if len(years) >= 2 else (1900, 2100)
top = int(opt("--top", "30"))
use = opt("--sources", "konomys,bunshun,honya").split(",")
SHORT = {"konomys": "このミス", "bunshun": "週刊文春ベスト10", "honya": "本屋大賞"}
KO = {"konomys": "이 미스터리가 대단해!", "bunshun": "주간문춘 미스터리 베스트10", "honya": "서점대상"}

works = defaultdict(lambda: dict(score=0, hits=[]))
for r in sources_ja.load_all():
    if r["source"] not in use or not (lo <= r["year"] <= hi):
        continue
    w = works[matching.jn(r["title"]) + "|" + r["author"]]
    w.update(title=w.get("title") or r["title"], author=r["author"])
    w["score"] += 11 - r["rank"]
    w["hits"].append(r)
ranked = sorted(works.values(), key=lambda w: (-w["score"], w["title"]))[:top]
if not ranked:
    sys.exit("소스 캐시가 비어 있습니다. 먼저 python scripts/sources_ja.py 를 실행하세요.")

info = matching.ja_author_info([w["author"] for w in ranked])
rows, unresolved = [], []
for w in ranked:
    item, how, ko_author = matching.find_korean_ja(w["title"], w["author"], info)
    hits = sorted(w["hits"], key=lambda h: (h["rank"], h["year"]))
    awards = " · ".join("%s %d %d위" % (SHORT[h["source"]], h["year"], h["rank"]) for h in hits)
    best = hits[0]
    summary = "%s %d년 %d위%s." % (KO[best["source"]], best["year"], best["rank"],
                                 " 등 랭킹 %d곳에 오른 작품" % len(hits) if len(hits) > 1 else "에 오른 작품")
    manual = matching.manual_ja().get(w["title"] + "|" + w["author"])
    if not item and manual is None:
        unresolved.append(dict(key=w["title"] + "|" + w["author"], reading=(info.get(w["author"]) or {}).get("kana"),
                               korean_author=ko_author, candidates=matching.ja_candidates(w["author"], info)))
    rows.append(dict(
        category="랭킹 %d곳 이상" % 2 if len({h["source"] for h in hits}) > 1 else KO[best["source"]],
        title=matching.base_title(item["title"]) if item else "", original=w["title"],
        author=ko_author or w["author"], author_orig=w["author"], lang="ja",
        awards=awards, summary=summary, grq="", note="", score=w["score"]))
    print("%3d점 %s / %s → %s (%s)" % (w["score"], w["title"], w["author"], item["title"] if item else "-", how))

label = " + ".join(SHORT[s] for s in use)
spec = dict(query="일본 랭킹 " + slug,
            title="일본 랭킹 상위작 — %s (%s~%s)" % (label, lo if lo > 1900 else "전체", hi if hi < 2100 else ""),
            subtitle="일본어 위키백과의 %s 연도별 1~10위를 집계해 점수순으로 뽑은 %d권. 순위마다 (11-순위)점." % (label, len(rows)),
            books=rows)
out = bd.DATA / "queries"
(out / (slug + ".json")).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
(out / (slug + ".unresolved.json")).write_text(json.dumps(unresolved, ensure_ascii=False, indent=1), encoding="utf-8")
found = sum(1 for r in rows if r["title"])
print("\n%d권 중 국내판 %d권 확인, 미해결 %d권 → data/queries/%s.unresolved.json" % (len(rows), found, len(unresolved), slug))
