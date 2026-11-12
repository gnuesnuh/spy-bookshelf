"""일본 랭킹(소스 캐시)을 추천 소스로 써서 질의별 추천 목록 data/queries/<slug>.json 을 만든다. 모델 호출 없음.

질의 두 가지
  제목:  python scripts/build_ja_list.py like-kokurojo --seed "흑뢰성" [--top 25]
         기준 도서(한국어 제목 또는 일본어 원제)를 랭킹에서 찾아, 함께 언급된 작품을 추천한다.
           · 같은 해 같은 랭킹에 함께 오른 작품 (순위가 높을수록 가점)
           · 같은 작가의 다른 랭킹 진입작
           · 기준 도서 앞뒤 3년의 랭킹 상위작 (낮은 가중치)
  장르:  python scripts/build_ja_list.py ja-mystery --genre mystery [시작연도 끝연도] [--top 30]
         장르에 맞는 랭킹만 골라 (11-순위)점을 더한 상위작. mystery → このミス·週刊文春, fiction → 本屋大賞

먼저 python scripts/sources_ja.py 로 소스 캐시를 만들어 둔다.
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


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


GENRES = {"mystery": ["konomys", "bunshun"], "fiction": ["honya"], "all": ["konomys", "bunshun", "honya"]}
GENRE_KO = {"mystery": "일본 미스터리", "fiction": "일본 소설(서점대상)", "all": "일본 소설·미스터리"}
SHORT = {"konomys": "このミス", "bunshun": "週刊文春ベスト10", "honya": "本屋大賞"}
KO = {"konomys": "이 미스터리가 대단해!", "bunshun": "주간문춘 미스터리 베스트10", "honya": "서점대상"}

slug = args[0]
seed = opt("--seed")
genre = opt("--genre", "all" if seed else "mystery")
top = int(opt("--top", "25" if seed else "30"))
years = [int(a) for a in args[1:] if a.isdigit() and len(a) == 4]
lo, hi = years[:2] if len(years) >= 2 else (1900, 2100)

rows_all = [r for r in sources_ja.load_all() if r["source"] in GENRES[genre]]
if not rows_all:
    sys.exit("소스 캐시가 비어 있습니다. 먼저 python scripts/sources_ja.py 를 실행하세요.")
key = lambda r: matching.jn(r["title"]) + "|" + r["author"]
works = defaultdict(lambda: dict(score=0.0, hits=[], why=[]))
for r in rows_all:
    w = works[key(r)]
    w.update(title=w.get("title") or r["title"], author=r["author"])
    w["hits"].append(r)


def find_seed(text):
    """기준 도서를 랭킹에서 찾는다. 한국어 제목이면 YES24 로 일본어 원제를 얻어 대조한다."""
    cands = [text] if matching.is_ja(text) else []
    if not cands:
        for i in matching.search(text, 1) or []:
            if matching.norm_ko(text) in matching.norm_ko(i.get("title")) and matching.is_ja(i.get("originalTitle")):
                cands.append(i["originalTitle"])
    for c in cands:
        for k, w in works.items():
            t = k.split("|")[0]
            if t == matching.jn(c) or (len(t) >= 4 and (t in matching.jn(c) or matching.jn(c) in t)):
                return k
    return None


if seed:
    sk = find_seed(seed)
    if not sk:
        sys.exit("기준 도서 '%s' 를 일본 랭킹(%s)에서 찾지 못했습니다. 일본어 원제로 다시 시도하거나 --genre 를 바꿔 보세요."
                 % (seed, ", ".join(SHORT[s] for s in GENRES[genre])))
    sw = works[sk]
    seed_lists = {(h["source"], h["year"]): h["rank"] for h in sw["hits"]}
    seed_years = [h["year"] for h in sw["hits"]]
    for k, w in works.items():
        if k == sk:
            continue
        for h in w["hits"]:
            if (h["source"], h["year"]) in seed_lists:          # 같은 해 같은 랭킹에 함께 오름
                w["score"] += 11 - h["rank"]
                w["why"].append("co")
            elif w["author"] == sw["author"]:                    # 같은 작가의 다른 진입작
                w["score"] += 3 + (11 - h["rank"]) * 0.3
                w["why"].append("author")
            elif min(abs(h["year"] - y) for y in seed_years) <= 3:   # 비슷한 시기 상위작
                w["score"] += (11 - h["rank"]) * 0.3
                w["why"].append("era")
    pool = sorted([w for k, w in works.items() if k != sk and w["score"] > 0], key=lambda w: (-w["score"], w["title"]))
    same, rest = 0, []
    for w in pool:   # 같은 작가 작품이 목록을 덮지 않게 5권까지만
        if w["author"] == sw["author"] and "co" not in w["why"]:
            same += 1
            if same > 5:
                continue
        rest.append(w)
    ranked = [sw] + rest[:top - 1]
    sw["why"] = ["seed"]
else:
    for w in works.values():
        w["score"] = sum(11 - h["rank"] for h in w["hits"] if lo <= h["year"] <= hi)
    ranked = sorted([w for w in works.values() if w["score"] > 0], key=lambda w: (-w["score"], w["title"]))[:top]

info = matching.ja_author_info([w["author"] for w in ranked])
rows, unresolved = [], []
seed_ko = None
for w in ranked:
    item, how, ko_author = matching.find_korean_ja(w["title"], w["author"], info)
    hits = sorted(w["hits"], key=lambda h: (h["rank"], h["year"]))
    awards = " · ".join("%s %d %d위" % (SHORT[h["source"]], h["year"], h["rank"]) for h in hits[:6])
    best = hits[0]
    ko_title = matching.base_title(item["title"]) if item else ""
    why = w.get("why") or []
    if "seed" in why:
        seed_ko = ko_title or w["title"]
        cat, summary = "기준 도서", "기준 도서. %s %d년 %d위." % (KO[best["source"]], best["year"], best["rank"])
    elif "co" in why:
        co = [h for h in w["hits"] if (h["source"], h["year"]) in seed_lists]
        c = min(co, key=lambda h: h["rank"])
        cat = "같은 해 함께 오른 작품"
        summary = "기준 도서와 같은 %d년 %s에서 %d위(기준 도서 %d위)%s." % (
            c["year"], KO[c["source"]], c["rank"], seed_lists[(c["source"], c["year"])],
            ", 함께 오른 랭킹 %d곳" % len(co) if len(co) > 1 else "")
    elif "author" in why:
        cat, summary = "같은 작가", "기준 도서와 같은 작가의 작품. %s %d년 %d위." % (KO[best["source"]], best["year"], best["rank"])
    elif "era" in why:
        cat, summary = "비슷한 시기 상위작", "기준 도서와 비슷한 시기의 랭킹 상위작. %s %d년 %d위." % (KO[best["source"]], best["year"], best["rank"])
    else:
        cat = "랭킹 2곳 이상" if len({h["source"] for h in hits}) > 1 else KO[best["source"]]
        summary = "%s %d년 %d위%s." % (KO[best["source"]], best["year"], best["rank"],
                                     " 등 랭킹 %d곳에 오른 작품" % len(hits) if len(hits) > 1 else "에 오른 작품")
    if not item and matching.manual_ja().get(w["title"] + "|" + w["author"]) is None:
        unresolved.append(dict(key=w["title"] + "|" + w["author"], reading=(info.get(w["author"]) or {}).get("kana"),
                               korean_author=ko_author, candidates=matching.ja_candidates(w["author"], info)))
    rows.append(dict(category=cat, title=ko_title, original=w["title"], author=ko_author or w["author"],
                     author_orig=w["author"], lang="ja", awards=awards, summary=summary, grq="", note="",
                     score=round(w["score"], 1)))
    print("%5.1f %s / %s → %s (%s) [%s]" % (w["score"], w["title"], w["author"], item["title"] if item else "-", how, cat))

srcs = " · ".join(KO[s] for s in GENRES[genre])
if seed:
    spec = dict(query=seed_ko, kind="title", seed=seed_ko,
                title="『%s』을 좋아했다면 — %s %d선" % (seed_ko, GENRE_KO[genre], len(rows)),
                subtitle="일본 랭킹(%s)에서 기준 도서와 같은 해에 함께 오른 작품, 같은 작가의 작품, 비슷한 시기 상위작을 모았다" % srcs)
else:
    span = "%d~%d년" % (lo, hi) if lo > 1900 else "역대"
    spec = dict(query=GENRE_KO[genre], kind="genre",
                title="%s — %s 랭킹 상위 %d선" % (GENRE_KO[genre], span, len(rows)),
                subtitle="장르 질의. 일본 랭킹(%s)의 연도별 1~10위에 (11-순위)점을 주고 합산한 상위작" % srcs)
spec["books"] = rows
out = bd.DATA / "queries"
(out / (slug + ".json")).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
(out / (slug + ".unresolved.json")).write_text(json.dumps(unresolved, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n%d권 중 국내판 %d권 확인, 미해결 %d권 → data/queries/%s.unresolved.json"
      % (len(rows), sum(1 for r in rows if r["title"]), len(unresolved), slug))
