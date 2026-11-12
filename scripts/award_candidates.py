"""소스 캐시(어워드·랭킹 DB)에서 질의의 '어워드 축' 후보를 뽑는다. 목록을 만들지 않는다. 모델 호출 없음.

질의 흐름(docs/PLAN.md 6절)의 2단계 '소스 수집'에서 쓰는 도구다. 사용자가 책이나 장르를 말했을 때 실행하고,
결과는 다른 근거(전문가 추천·언론 결산·커뮤니티·Reddit(Gemini 경유))와 함께 Claude Code 가 집계해
data/queries/<slug>.json 목록을 만든다. 이 스크립트 혼자서는 '근거 소스 1종류'일 뿐이다.

제목:  python scripts/award_candidates.py <slug> --seed "흑뢰성" [--genre mystery] [--top 40]
         기준 도서(한국어 제목·영어 원제·일본어 원제)를 소스에서 찾아
         · 같은 해 같은 소스에 함께 오른 작품 · 같은 작가의 다른 수상·진입작(5권까지) · 같은 장르 앞뒤 3년 상위작
장르:  python scripts/award_candidates.py <slug> --genre mystery [시작연도 끝연도] [--top 40] [--region en,ja]

점수 (× 소스 가중치, scripts/sources.json): 순위형 (11-순위) · 수상 10 · 후보 4
      지역마다 소스 수가 달라 점수 크기가 다르므로, 장르 질의는 지역 안의 최고점을 100으로 맞춘 뒤 섞는다.
      판매량 소스(bestseller)는 장르 소스에 이미 오른 작품의 가점으로만 쓴다.
장르: mystery, spy, sf, literary, nonfiction, business, science, history, bestseller  (등록부의 genres)
먼저 python scripts/sources.py 로 소스 캐시를 만들어 둔다. 소스 목록은 docs/SOURCES.md.

출력
  data/queries/<slug>.awards.json      후보: 원제·저자, 수상·순위 이력(awards), 점수, 찾은 국내 제목·저자
  data/queries/<slug>.unresolved.json  국내판을 자동으로 못 찾은 일본 책 + 같은 저자의 '원제 미표기' 국내 출간작 후보
                                       → Claude Code 가 보고 scripts/ja_titles.json 에 판정을 적은 뒤 다시 실행
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
args = [a for a in sys.argv[1:] if a != "--refresh"]
import build_data as bd  # noqa: E402
import matching  # noqa: E402
import sources  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


GENRE_KO = dict(mystery="미스터리·스릴러", spy="첩보", sf="SF", literary="문학", nonfiction="논픽션", business="경제·경영",
                science="과학", history="역사", bestseller="베스트셀러")
REGION_KO = dict(en="영미권", ja="일본")
slug = args[0]
seed = opt("--seed")
genre = opt("--genre")
regions = (opt("--region") or "en,ja").split(",")
top = int(opt("--top", "25" if seed else "30"))
years = [int(a) for a in args[1:] if a.isdigit() and len(a) == 4]
lo, hi = years[:2] if len(years) >= 2 else (1900, 2100)

REG = {s["id"]: s for s in sources.registry()}


def use_source(s, g):
    return s["lang"] in regions and (g is None or g in s["genres"])


def points(r):
    w = REG[r["source"]].get("weight", 1)
    return w * ((11 - r["rank"]) if r["result"] == "rank" and r["rank"] else 10 if r["result"] == "win" else 4)


def wkey(r):
    if r["lang"] == "ja":
        return "ja|" + matching.jn(r["title"]) + "|" + r["author"]
    return "en|" + matching.en(r["title"]) + "|" + matching.en(r["author"].split()[-1] if r["author"].split() else r["author"])


def load_works(g):
    works = {}
    for r in sources.load([i for i, s in REG.items() if use_source(s, g)]):
        w = works.setdefault(wkey(r), dict(score=0.0, hits=[], why=[], title=r["title"], author=r["author"], lang=r["lang"]))
        w["hits"].append(r)
    if g and g != "bestseller":   # 판매량 소스는 장르가 맞는 작품에만 가점으로 붙인다(자기계발서 등이 섞이지 않게)
        for r in sources.load([i for i, s in REG.items() if s["lang"] in regions and "bestseller" in s["genres"]
                               and g not in s["genres"]]):
            if wkey(r) in works:
                works[wkey(r)]["hits"].append(r)
    return works


def label(h):
    name = REG[h["source"]]["name"].split(" (")[0]
    if h["result"] == "rank":
        return "%s %d %d위" % (name, h["year"], h["rank"])
    return "%s %d %s" % (name, h["year"], "수상" if h["result"] == "win" else "후보")


def find_seed(works, text):
    """기준 도서를 소스에서 찾는다. 한국어 제목이면 YES24 로 원제(영어·일본어)를 얻어 대조한다."""
    cands = [text]
    if re.search("[가-힣]", text):
        cands = [i["originalTitle"] for i in matching.search(text, 1) or []
                 if matching.norm_ko(text) in matching.norm_ko(i.get("title")) and i.get("originalTitle")]
    for c in cands:
        ja = matching.is_ja(c)
        t = matching.jn(c) if ja else matching.en(c)
        for k, w in works.items():
            lang, wt = k.split("|")[0], k.split("|")[1]
            if (lang == "ja") != ja or not wt:
                continue
            if wt == t or (min(len(wt), len(t)) >= (4 if ja else 10) and (wt in t or t in wt)):
                return k
    return None


INFO = {}


def match(w):
    """국내판 찾기(결과를 작품에 붙여 둔다) → (YES24 상품 또는 None, 근거, 한국어 저자명)."""
    if "m" not in w:
        if w["lang"] == "ja":
            if w["author"] not in INFO:
                INFO.update(matching.ja_author_info([w["author"]]))
            w["m"] = matching.find_korean_ja(w["title"], w["author"], INFO)
        else:
            w["m"] = matching.find_korean_en(w["title"], w["author"])
    return w["m"]


if seed:
    works = load_works(genre)
    sk = find_seed(works, seed)
    if not sk and genre:   # 지정한 장르 소스에 없으면 전체 소스에서 찾고, 그 책이 오른 소스의 장르를 따른다
        works = load_works(None)
        sk = find_seed(works, seed)
    if not sk:
        sys.exit("기준 도서 '%s' 를 소스에서 찾지 못했습니다(어워드·랭킹에 오른 적이 없는 책). 원제로 다시 시도해 보세요." % seed)
    sw = works[sk]
    seed_genres = {g for h in sw["hits"] for g in REG[h["source"]]["genres"]}
    seed_lists = {(h["source"], h["year"]): h for h in sw["hits"]}
    seed_years = [h["year"] for h in sw["hits"]]
    for k, w in works.items():
        if k == sk:
            continue
        for h in w["hits"]:
            if (h["source"], h["year"]) in seed_lists:
                w["score"] += points(h)
                w["why"].append("co")
            elif w["lang"] == sw["lang"] and w["author"] == sw["author"]:
                w["score"] += 3 + points(h) * 0.3
                w["why"].append("author")
            elif min(abs(h["year"] - y) for y in seed_years) <= 3 and seed_genres & set(REG[h["source"]]["genres"]):
                w["score"] += points(h) * 0.3
                w["why"].append("era")
    pool = sorted([w for k, w in works.items() if k != sk and w["score"] > 0], key=lambda w: (-w["score"], w["title"]))
    same, rest = 0, []
    for w in pool:   # 같은 작가 작품이 목록을 덮지 않게 5권까지만
        if w["author"] == sw["author"] and "co" not in w["why"]:
            same += 1
            if same > 5:
                continue
        rest.append(w)
    other = [w for w in rest if w["lang"] != sw["lang"]][:max(3, top // 4)]   # 다른 지역 작품도 1/4 정도 섞는다
    mine = [w for w in rest if w["lang"] == sw["lang"]][:top - 1 - len(other)]
    sw["why"] = ["seed"]
    ranked = [sw] + sorted(mine + other, key=lambda w: -w["score"])
else:
    works = load_works(genre)
    for w in works.values():
        w["score"] = sum(points(h) for h in w["hits"] if lo <= h["year"] <= hi)
    live = [r for r in regions if any(w["lang"] == r and w["score"] > 0 for w in works.values())]
    ranked = []
    for i, r in enumerate(live):   # 지역별로 같은 수만큼 뽑는다
        n = top // len(live) + (1 if i < top % len(live) else 0)
        cand = sorted([w for w in works.values() if w["lang"] == r and w["score"] > 0],
                      key=lambda w: (-w["score"], w["title"]))[:n * 4]
        INFO.update(matching.ja_author_info([w["author"] for w in cand if w["lang"] == "ja"]))
        # 국내판 있는 책을 우선 뽑고, 미번역은 점수 높은 순으로 1/5 까지만 '미번역 명작'으로 싣는다
        keep_miss = max(1, n // 5)
        got, miss = [], []
        for w in cand:
            if match(w)[0]:
                got.append(w)
            elif len(miss) < keep_miss:
                w["untranslated"] = True
                miss.append(w)
            if len(got) >= n - keep_miss and len(miss) >= keep_miss:
                break
        ranked += got[:n - len(miss)] + miss
    # 지역마다 소스 수와 형식이 달라 점수 크기가 다르다 → 지역 안의 최고점을 100으로 맞춰 섞는다
    for r in live:
        mx = max(w["score"] for w in ranked if w["lang"] == r)
        for w in ranked:
            if w["lang"] == r:
                w["norm"] = w["score"] / mx * 100
    ranked.sort(key=lambda w: (bool(w.get("untranslated")), -w.get("norm", 0)))   # 읽을 수 있는 책 먼저, 미번역은 뒤에
if not ranked:
    sys.exit("조건에 맞는 소스 항목이 없습니다. 먼저 python scripts/sources.py 를 실행했는지, 장르 이름이 맞는지 확인하세요.")

INFO.update(matching.ja_author_info([w["author"] for w in ranked if w["lang"] == "ja"]))
info = INFO
rows, unresolved, seed_ko = [], [], None
for w in ranked:
    item, how, ko_author = match(w)
    hits = sorted(w["hits"], key=lambda h: (-points(h), -h["year"]))
    best = hits[0]
    ko_title = matching.base_title(item["title"]) if item else ""
    why = w.get("why") or []
    region = REGION_KO[w["lang"]]
    if "seed" in why:
        seed_ko = ko_title or w["title"]
        cat, summary = "기준 도서", "기준 도서. %s." % label(best)
    elif "co" in why:
        co = sorted([h for h in w["hits"] if (h["source"], h["year"]) in seed_lists], key=lambda h: -points(h))
        s0 = seed_lists[(co[0]["source"], co[0]["year"])]
        cat = "같은 해 함께 오른 작품"
        summary = "기준 도서와 같은 해 같은 소스: %s (기준 도서는 %s)%s." % (
            label(co[0]), label(s0).split(" ", 1)[1] if " " in label(s0) else label(s0),
            ", 겹친 소스 %d곳" % len(co) if len(co) > 1 else "")
    elif "author" in why:
        cat, summary = "같은 작가", "기준 도서와 같은 작가의 작품. %s." % label(best)
    elif "era" in why:
        cat = "비슷한 시기 상위작" if w["lang"] == sw["lang"] else "비슷한 시기 %s 상위작" % region
        summary = "기준 도서와 같은 장르, 비슷한 시기의 %s 작품. %s%s." % (region, label(best), " 외 %d건" % (len(hits) - 1) if len(hits) > 1 else "")
    else:
        cat = ("미번역 명작 (%s)" % region) if w.get("untranslated") else region
        summary = "%s%s." % (label(best), " 외 %d건에 오른 작품" % (len(hits) - 1) if len(hits) > 1 else "")
    if w["lang"] == "ja" and not item and matching.manual_ja().get(w["title"] + "|" + w["author"]) is None:
        unresolved.append(dict(key=w["title"] + "|" + w["author"], reading=(info.get(w["author"]) or {}).get("kana"),
                               korean_author=ko_author, candidates=matching.ja_candidates(w["author"], info)))
    rows.append(dict(category=cat, title=ko_title, original=w["title"], author=ko_author or w["author"],
                     author_orig=w["author"], lang=w["lang"], awards=" · ".join(label(h) for h in hits[:6]),
                     summary=summary, grq=re.split(r"[:(]", w["title"])[0].strip() if w["lang"] == "en" else "", note="",
                     score=round(w.get("norm", w["score"]), 1)))
    print("%5.1f [%s] %s / %s → %s (%s) [%s]" % (w["score"], w["lang"], w["title"][:34], w["author"][:18],
                                                 item["title"][:22] if item else "-", how, cat))

used = sorted({h["source"] for w in ranked for h in w["hits"]}, key=lambda i: (REG[i]["lang"], i))
src_txt = ", ".join(REG[i]["name"].split(" (")[0] for i in used[:10]) + (" 외 %d곳" % (len(used) - 10) if len(used) > 10 else "")
gk = GENRE_KO.get(genre, genre) if genre else "전 장르"
if seed:
    spec = dict(query=seed_ko, kind="title", seed=seed_ko, title="『%s』을 좋아했다면 — %d선" % (seed_ko, len(rows)),
                subtitle="기준 도서와 같은 해 같은 소스에 함께 오른 작품, 같은 작가의 작품, 같은 장르의 비슷한 시기 상위작. 소스: " + src_txt)
else:
    span = "%d~%d년" % (lo, hi) if lo > 1900 else "역대"
    spec = dict(query=gk, kind="genre", title="%s — %s %s 상위 %d선" % (gk, " + ".join(REGION_KO[r] for r in regions), span, len(rows)),
                subtitle="장르 질의. 어워드 수상 10점·후보 4점, 랭킹 (11-순위)점에 소스 가중치를 곱해 합산. 소스: " + src_txt)
out = bd.DATA / "queries"
cands = dict(axis="awards", kind=spec["kind"], query=spec["query"], note=spec["subtitle"], sources=used, candidates=rows)
(out / (slug + ".awards.json")).write_text(json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
(out / (slug + ".unresolved.json")).write_text(json.dumps(unresolved, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n어워드 축 후보 %d권 (영미권 %d, 일본 %d) 중 국내판 %d권 확인, 일본 미해결 %d권 · 쓴 소스 %d곳"
      % (len(rows), sum(1 for r in rows if r["lang"] == "en"), sum(1 for r in rows if r["lang"] == "ja"),
         sum(1 for r in rows if r["title"]), len(unresolved), len(used)))
print("→ data/queries/%s.awards.json  (목록이 아니라 후보다. 다른 근거와 합쳐 %s.json 을 만든다)" % (slug, slug))
