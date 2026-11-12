"""단계 3 집계. 한 질의의 근거 파일을 모두 읽어 원제 기준으로 묶고 근거 수를 센다. 판단(축 적합성)은 하지 않는다.
사용법: python scripts/aggregate.py <slug> [--min 1]

읽는 파일 (있는 것만)
  data/sources/web/<slug>.json          웹에서 읽은 페이지(전문가·언론·목록). 형식: prompts/2_collect_sources.md
  data/queries/<slug>.awards.json       award_candidates.py 결과 — 어워드 이름마다 근거 1곳
  data/community/<slug>.gemini.json     gemini_candidates.py 결과 — reddit_cited 인 책만, 'Reddit(Gemini 경유)' 1곳
  data/community/<slug>.json            community_fetch.py 원문 — 이미 후보가 된 책의 원제가 글에 나오면 플랫폼(HN 등)마다 1곳
                                        (커뮤니티 원문에서 새 후보를 뽑지는 않는다: 제목 추출이 불확실해서)
출력  data/queries/<slug>.rank.json   [{original, author, sources[], kinds[], n, n_kinds, axes[]}] 근거 수·종류 수 순
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from matching import en  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
slug = sys.argv[1]
MIN = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 1
COMM = {"hn": "Hacker News", "discourse": "Discourse", "lemmy": "Lemmy"}


def load(p):
    p = ROOT / p
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


ORD = {"1st": "first", "2nd": "second", "3rd": "third", "4th": "fourth", "5th": "fifth", "6th": "sixth",
       "7th": "seventh", "8th": "eighth", "9th": "ninth", "10th": "tenth"}


def main_key(title):
    t = re.sub(r"\b(\d+(?:st|nd|rd|th))\b", lambda m: ORD.get(m.group(1).lower(), m.group(1)), title or "", flags=re.I)
    return en(re.split(r"[:：]", t)[0])


def last(author):
    a = re.sub(r"\(.*?\)|\b(jr|sr|phd|md)\b\.?", "", (author or "").lower())
    w = re.findall(r"[a-z]+", a.split(",")[0].split("&")[0].split(" and ")[0])
    return w[-1] if w else ""


works = []  # {key, last, original, author, sources{name: kind}, axes set}


def add(title, author, source, kind, axis=None):
    k, l = main_key(title), last(author)
    if len(k) < 3:
        return
    for w in works:
        if w["key"] == k and (not l or not w["last"] or l == w["last"]):
            break
    else:
        w = dict(key=k, last=l, original=title.strip(), author=(author or "").strip(), sources={}, axes=set())
        works.append(w)
    if len(title) > len(w["original"]):
        w["original"] = title.strip()  # 부제까지 있는 긴 원제를 남긴다(매칭에 유리)
    if not w["author"] and author:
        w["author"], w["last"] = author.strip(), l
    w["sources"].setdefault(source, kind)
    if axis:
        w["axes"].add(axis)


used = []
web = load("data/sources/web/%s.json" % slug) or []
for e in web:
    for b in e["books"]:
        add(b[0], b[1] if len(b) > 1 else "", e["source"], e["kind"], e.get("for_axis"))
if web:
    used.append("웹 %d페이지" % len(web))

aw = load("data/queries/%s.awards.json" % slug)
if aw:
    for c in aw.get("candidates", []):
        if c.get("category") == "기준 도서":
            continue
        for lab in (c.get("awards") or "").split(" · "):
            name = re.split(r"\s+(?:19|20)\d\d", lab)[0].strip()
            if name:
                add(c["original"], c.get("author_orig") or "", name, "award")
    used.append("어워드 %d후보" % len(aw.get("candidates", [])))

gm = load("data/community/%s.gemini.json" % slug)
if gm:
    for b in gm.get("books", []):
        if b.get("reddit_cited"):
            add(b["title"], b.get("author") or "", "Reddit(Gemini 경유)", "community")
    used.append("Gemini %d권" % len(gm.get("books", [])))

cm = load("data/community/%s.json" % slug)
if cm:
    texts = {}
    for it in cm.get("items", []):
        texts.setdefault(it["source"], []).append(en((it.get("thread") or "") + " " + (it.get("text") or "")))
    for w in works:
        for src, ts in texts.items():
            k = w["key"]
            # 짧은 제목(15자 미만, 예: Rationality)은 일반 단어와 겹쳐 오검출이 많으므로 저자 성까지 함께 나와야 센다
            hit = any(k in t and (len(k) >= 15 or (w["last"] and w["last"] in t)) for t in ts)
            if hit:
                w["sources"].setdefault(COMM.get(src, src), "community")
    used.append("커뮤니티 원문 %d건" % len(cm.get("items", [])))

seed = None
ax = load("data/queries/%s.axes.json" % slug)
if ax:
    seed = main_key(ax["seed"]["original"])
rows = []
for w in works:
    if w["key"] == seed:
        continue
    kinds = sorted(set(w["sources"].values()))
    rows.append(dict(original=w["original"], author=w["author"], sources=list(w["sources"]), kinds=kinds,
                     n=len(w["sources"]), n_kinds=len(kinds), axes=sorted(w["axes"])))
rows = [r for r in rows if r["n"] >= MIN]
rows.sort(key=lambda r: (-r["n"], -r["n_kinds"], r["original"]))
(ROOT / "data/queries" / (slug + ".rank.json")).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("입력:", ", ".join(used) or "없음", "→ 후보 %d권" % len(rows))
for r in rows[:60]:
    print("%2d곳 %d종 %-45s %-22s %s" % (r["n"], r["n_kinds"], r["original"][:45], r["author"][:22], " · ".join(r["sources"])[:90]))
