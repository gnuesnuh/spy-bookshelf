"""추천 소스(어워드·랭킹) 수집기. 등록부 scripts/sources.json 에 적힌 소스를 위키백과에서 받아
data/sources/<id>.json 으로 저장하고(소스 캐시), 소스 목록 문서 docs/SOURCES.md 를 다시 만든다.

사용법:  python scripts/sources.py                 (등록부의 모든 소스. 이미 받은 페이지는 캐시 사용)
        python scripts/sources.py edgar hugo      (지정한 소스만)
        python scripts/sources.py --refresh       (위키백과에서 다시 받기 — 새 연도가 추가됐을 때)
        python scripts/sources.py --probe en:"Gold Dagger"   (새 소스를 등록하기 전에 표 구조 보기)

항목 형식: {source, year, rank, result, title, author, lang}
  rank    순위형 소스의 순위(1~10). 수상형 소스는 None
  result  "win"(수상) / "nom"(후보·최종후보) / "rank"(순위형)
수상 결과는 바뀌지 않으므로 한 번 받으면 다시 받을 필요가 없다.

등록부 항목 (scripts/sources.json)
  id, name, lang(en|ja), page(위키백과 문서명), genres[...], kind(award|ranking|press), weight,
  parser: "table"(표의 열 이름으로 연도·제목·저자·결과 열을 찾는다) | "ja_ranked"(このミス 식 '# 제목（저자）' 목록) | "honya"
  선택: tables(쓸 표 번호 목록), cols{year,title,author,result}(열 이름에 들어갈 문자열을 직접 지정),
        all_win(true 면 표의 모든 행을 수상으로 본다), note
"""
import html as htmllib
import json
import re
import sys
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_data as bd  # noqa: E402

bd.GAP.update({"en.wikipedia.org": 4.0, "ja.wikipedia.org": 4.0})   # 위키백과는 몰아서 부르면 429 를 준다
ROOT = bd.ROOT
OUT = bd.DATA / "sources"
REG = ROOT / "scripts" / "sources.json"

HINT = dict(
    year=["year", "年", "回", "date", "ceremony", "award"],
    title=["title", "work", "novel", "book", "nominee", "winner", "作品", "受賞作", "書名", "題", "タイトル", "候補作"],
    author=["author", "writer", "recipient", "著者", "作者", "受賞者", "作家", "候補者", "筆者"],
    result=["result", "結果", "status", "outcome"],
)
WIN = re.compile(r"\bwin|winner|won\b|受賞|大賞|^1$", re.I)
NOM = re.compile(r"nomin|shortlist|finalist|longlist|候補|最終|入選|runner", re.I)


class Tables(HTMLParser):
    """위키백과 HTML 에서 wikitable 을 뽑는다. rowspan·colspan 을 펼치고, 셀이 굵은 글씨인지도 기록한다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.t, self.row, self.cell = [], None, None, None
        self.depth, self.skip, self.heading, self.h = 0, 0, "", None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("h2", "h3", "h4"):
            self.h = ""
        if tag == "table":
            self.depth += 1
            if self.depth == 1 and "wikitable" in (a.get("class") or ""):
                self.t = dict(rows=[], heading=self.heading.strip())
        elif self.t is not None and self.depth == 1:
            if tag == "tr":
                self.row = []
            elif tag in ("td", "th") and self.row is not None:
                self.cell = dict(text="", th=tag == "th", bold=False, rs=int(re.sub(r"\D", "", a.get("rowspan") or "1") or 1),
                                 cs=int(re.sub(r"\D", "", a.get("colspan") or "1") or 1),
                                 bg=(a.get("style") or "") + (a.get("bgcolor") or ""))
            elif self.cell is not None:
                if tag in ("b", "strong"):
                    self.cell["bold"] = True
                elif tag in ("sup", "style", "script"):
                    self.skip += 1
                elif tag == "br":
                    self.cell["text"] += " / "

    def handle_endtag(self, tag):
        if tag in ("h2", "h3", "h4") and self.h is not None:
            self.heading, self.h = self.h, None
        if tag == "table":
            if self.depth == 1 and self.t is not None:
                self.tables.append(self.t)
                self.t = None
            self.depth = max(0, self.depth - 1)
        elif self.t is not None and self.depth == 1:
            if tag in ("td", "th") and self.cell is not None:
                self.cell["text"] = re.sub(r"\s+", " ", self.cell["text"]).strip(" /")
                self.row.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.t["rows"].append(self.row)
                self.row = None
            elif tag in ("sup", "style", "script") and self.skip:
                self.skip -= 1

    def handle_data(self, data):
        if self.h is not None:
            self.h += data
        if self.cell is not None and not self.skip:
            self.cell["text"] += data


def grid(table):
    """rowspan·colspan 을 펼친 2차원 표."""
    out, carry = [], {}
    for row in table["rows"]:
        line, ci, cells = [], 0, list(row)
        while cells or ci in carry:
            if ci in carry:
                c, left = carry[ci]
                line.append(c)
                carry[ci] = (c, left - 1)
                if left - 1 <= 0:
                    del carry[ci]
                ci += 1
                continue
            c = cells.pop(0)
            for k in range(c["cs"]):
                line.append(c)
                if c["rs"] > 1:
                    carry[ci + k] = (c, c["rs"] - 1)
            ci += c["cs"]
        out.append(line)
    return out


def page_html(lang, page):
    raw = bd.fetch("https://%s.wikipedia.org/w/api.php?format=json&action=parse&prop=text&redirects=1&page=%s"
                   % (lang, urllib.parse.quote(page)))
    if raw is None:
        return None
    d = json.loads(raw)
    return (d.get("parse") or {}).get("text", {}).get("*")


def tables_of(lang, page):
    h = page_html(lang, page)
    if h is None:
        return None
    p = Tables()
    p.feed(h)
    return p.tables


def find_col(header, names):
    for i, h in enumerate(header):
        if any(n.lower() in h.lower() for n in names):
            return i
    return None


def clean_title(s):
    s = re.sub(r"\[[^\]]*\]", "", s or "")
    s = s.split(" / ")[0] if " / " in s and len(s) > 80 else s
    return s.strip(" \"“”'‘’『』「」*†‡")


def parse_table_source(src, tables):
    rows = []
    use = src.get("tables")
    for ti, t in enumerate(tables):
        if use is not None and ti not in use:
            continue
        g = grid(t)
        if len(g) < 3:
            continue
        hi = next((i for i, r in enumerate(g[:3]) if r and all(c["th"] for c in r)), 0)
        header = [c["text"] for c in g[hi]]
        over = src.get("cols", {})
        cols = {k: (over[k] if isinstance(over.get(k), int) else find_col(header, [over[k]] if over.get(k) else HINT[k]))
                for k in HINT}
        body = g[hi + 1:]
        # 연도 열: 실제로 4자리 연도가 들어 있는 열을 고른다(直木賞의 '回' 열처럼 이름만 맞는 열 제외)
        ok = [i for i in range(len(header)) if i not in (cols["title"], cols["author"])
              and sum(1 for r in body[:6] if i < len(r) and re.search(r"(19|20)\d\d", r[i]["text"])) >= min(3, len(body[:6]))]
        cols["year"] = cols["year"] if cols["year"] in ok else (ok[0] if ok else None)
        hy = re.search(r"(19|20)\d\d", t["heading"])
        rank_col = find_col(header, ["順位", "rank"])
        if cols["title"] is None or cols["author"] is None:
            continue
        if cols["title"] == cols["author"]:
            continue
        year = int(hy.group(0)) if hy and cols["year"] is None else None
        for r in body:
            if len(r) <= max(cols["title"], cols["author"]):
                continue
            ytxt = r[cols["year"]]["text"] if cols["year"] is not None and cols["year"] < len(r) else ""
            m = re.search(r"(19|20)\d\d", ytxt)
            year = int(m.group(0)) if m else year
            title, author = clean_title(r[cols["title"]]["text"]), clean_title(r[cols["author"]]["text"])
            if not title or not author or not year or title.lower() in ("no award", "not awarded", "該当作なし", "受賞作なし"):
                continue
            res = r[cols["result"]]["text"] if cols["result"] is not None and cols["result"] < len(r) else ""
            tc = r[cols["title"]]
            star = any(r[cols[k]]["text"].rstrip(" ‡†").endswith("*") for k in ("title", "author"))   # Hugo 식 '저자*' 수상 표시
            if src.get("all_win") or star:
                result = "win"
            elif res:
                result = "win" if WIN.search(res) else "nom"
            else:   # 결과 열이 없으면 굵은 글씨·배경색을 수상 표시로 본다
                result = "win" if (tc["bold"] or r[cols["author"]]["bold"] or "background" in tc["bg"]) else "nom"
            rank = None
            if rank_col is not None and rank_col < len(r):   # 순위형 표(新書大賞): 大賞 = 1위
                rt = r[rank_col]["text"]
                d = re.search(r"\d+", rt)
                rank = 1 if "大賞" in rt else int(d.group(0)) if d else None
                if rank is None or rank > 10:
                    continue
                result = "rank"
            rows.append(dict(source=src["id"], year=year, rank=rank, result=result, title=title,
                             author=re.sub(r"\s*\(.*?\)", "", author).strip(), lang=src["lang"]))
    # 표에 굵은 글씨 구분이 전혀 없으면(전부 nom) 수상작 목록으로 본다
    if rows and not any(r["result"] in ("win", "rank") for r in rows) and not src.get("nom_only"):
        for r in rows:
            r["result"] = "win"
    seen, uniq = set(), []
    for r in rows:
        k = (r["year"], r["title"].lower(), r["author"].lower())
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def parse_list_source(src, text):
    """표가 아니라 목록으로 적힌 문서(日本推理作家協会賞, Women's Prize 등)를 위키텍스트에서 읽는다.

    일본어: 『제목』 과 그 앞의 저자.  영어: ''제목'' 과 [[저자]] 또는 'by 저자'.
    연도는 줄 앞부분이나 바로 위 제목 줄에서 얻는다. '#' 목록은 순위로 본다(src.ranked).
    """
    import sources_ja
    rows, year, n = [], None, 0
    for line in text.splitlines():
        h = re.match(r"^=+\s*(.*?)\s*=+\s*$", line)
        if h:
            m = re.search(r"(19|20)\d\d", h.group(1))
            if m:
                year, n = int(m.group(0)), 0
            continue
        if not line.startswith(("*", "#", ":", ";")):
            continue
        body = line.lstrip("*#:; ")
        m = re.search(r"(19|20)\d\d", body[:45])
        y = int(m.group(0)) if m else year
        if src["lang"] == "ja":
            titles = re.findall(r"『(.+?)』", body)
            if not titles:
                if m:           # '* 第1回（1970年）' 처럼 연도만 있는 줄 → 아래 줄들의 연도
                    year, n = int(m.group(0)), 0
                continue
            pre = sources_ja.plain(body.split("『")[0])
            pre = re.sub(r"第?\s*\d+\s*回|[（(]?\s*(19|20)\d\d\s*年度?[^）)]*[)）]?|受賞作?|候補作?|[-–—:：、。\s]", " ", pre).strip()
            if not pre or re.search("部門|賞|新聞|年|月|回", pre):   # 앞부분이 부문명·출처면 제목 뒤의 저자를 쓴다
                m2 = re.search(r"』\s*[（(]?\s*\[*([^\]|（()）、。『]+)", body)
                pre = sources_ja.plain(m2.group(1)) if m2 else ""
                if re.search("部門|賞|新聞|年|月|社$|書房$|出版$", pre):
                    pre = ""
            title, author = sources_ja.plain(titles[0]), pre.split()[0] if pre else ""
            win = "候補" not in body
        else:
            m3 = re.search(r"''+(.+?)''+", body)
            if not m3:
                if m:
                    year, n = int(m.group(0)), 0
                continue
            title = sources_ja.plain(m3.group(1))
            rest = body.replace(m3.group(0), " ")
            by = re.search(r"\bby\s+(.+)$", sources_ja.plain(rest))
            links = [x for x in re.findall(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", rest) if not re.fullmatch(r"\d{4}.*", x)]
            author = (by.group(1) if by else links[0] if links else re.sub(r"(19|20)\d\d|[–—:,\-]", " ", sources_ja.plain(rest))).strip()
            author = re.split(r"\s*[(\[]", author)[0].strip(" .,")
            win = "\'\'\'" in body or bool(src.get("all_win")) or bool(re.search(r"winner", body, re.I))
        if not y or not title or not author or len(author) > 60:
            continue
        rank = None
        if src.get("ranked") and line.startswith("#"):
            n += 1
            rank = n
            if rank > 10:
                continue
        rows.append(dict(source=src["id"], year=y, rank=rank, result="rank" if rank else ("win" if win else "nom"),
                         title=clean_title(title), author=author, lang=src["lang"]))
    if rows and not any(r["result"] in ("win", "rank") for r in rows):
        for r in rows:
            r["result"] = "win"
    return rows


def collect(src):
    if src["parser"] == "list":
        import sources_ja
        raw = bd.fetch("https://%s.wikipedia.org/w/api.php?format=json&action=parse&prop=wikitext&redirects=1&page=%s"
                       % (src["lang"], urllib.parse.quote(src["page"])))
        if raw is None:
            return None
        return parse_list_source(src, (json.loads(raw).get("parse") or {}).get("wikitext", {}).get("*", ""))
    if src["parser"] in ("ja_ranked", "honya"):
        import sources_ja
        text = sources_ja.wikitext(src["page"])
        if text is None:
            return None
        rows = sources_ja.parse_honya(text) if src["parser"] == "honya" else sources_ja.parse_ranked_lists(text, src["id"])
        return [dict(r, source=src["id"], result="rank", lang="ja") for r in rows]
    tables = tables_of(src["lang"], src["page"])
    if tables is None:
        return None
    return parse_table_source(src, tables)


def registry():
    return json.loads(REG.read_text(encoding="utf-8"))


def load(ids=None):
    """저장된 소스 캐시를 읽는다 → 항목 목록."""
    rows = []
    for s in registry():
        if s.get("disabled") or (ids is not None and s["id"] not in ids):
            continue
        f = OUT / (s["id"] + ".json")
        if f.exists():
            rows += json.loads(f.read_text(encoding="utf-8"))
    return rows


def write_doc(reg, stats):
    kinds = {"award": "어워드", "ranking": "연간 랭킹", "press": "언론·서점 선정"}
    lines = ["# 추천 소스 목록", "",
             "이 문서는 `python scripts/sources.py` 가 등록부 `scripts/sources.json` 에서 자동으로 만든다. 직접 고치지 말고 등록부를 고친다.",
             "소스를 추가하려면: `python scripts/sources.py --probe 언어:\"문서명\"` 으로 표 구조를 보고 → 등록부에 항목 추가 → `python scripts/sources.py <id>` 로 건수·표본을 확인한다.",
             "", "상태: ✅ 수집됨 · ⚠️ 수집됐지만 건수가 적음(표 일부만 읽힘) · ❌ 못 읽음", ""]
    for lang, label in (("en", "영미권"), ("ja", "일본")):
        lines += ["## %s" % label, "", "| 상태 | 소스 | 종류 | 장르 | 연도 | 건수(수상) | 가중치 | 비고 |", "|---|---|---|---|---|---|---|---|"]
        for s in [x for x in reg if x["lang"] == lang]:
            st = stats.get(s["id"]) or {}
            n = st.get("n", 0)
            mark = "❌" if not n else "⚠️" if n < 15 else "✅"
            lines.append("| %s | [%s](https://%s.wikipedia.org/wiki/%s) `%s` | %s | %s | %s | %s | %s | %s |" % (
                mark, s["name"], s["lang"], urllib.parse.quote(s["page"].replace(" ", "_")), s["id"],
                kinds.get(s["kind"], s["kind"]), ", ".join(s["genres"]),
                ("%s~%s" % (st["lo"], st["hi"])) if n else "-", ("%d (%d)" % (n, st.get("win", 0))) if n else "0",
                s.get("weight", 1), s.get("note", "")))
        lines.append("")
    lines += ["## 아직 못 넣은 소스", "",
              "- 독자 커뮤니티: Reddit(403, 공식 API 필요), 読書メーター·ブクログ(자동 접근 거부). Hacker News·Discourse 는 `scripts/community_fetch.py`.",
              "- 언론 연간 결산(NYT 10 Best, Guardian, 朝日·読売 書評 '今年の3冊' 등): 위키백과에 표가 없어 페이지별 수집기가 필요하다.",
              "- Goodreads Choice Awards: 위키백과에 후보 목록이 없다.", ""]
    (ROOT / "docs" / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if a != "--refresh"]
    if args and args[0] == "--probe":
        lang, page = args[1].split(":", 1)
        tables = tables_of(lang, page.strip('"'))
        if tables is None:
            sys.exit("확인 불가 (위키백과 조회 실패)")
        for i, t in enumerate(tables):
            g = grid(t)
            if len(g) < 3:
                continue
            print("[표 %d] %s | %d행 | 열: %s" % (i, t["heading"][:30], len(g), [c["text"][:14] for c in g[0]]))
            for r in g[1:3]:
                print("     ", [("*" if c["bold"] else "") + c["text"][:22] for c in r])
        return
    OUT.mkdir(parents=True, exist_ok=True)
    reg = registry()
    stats = {}
    for s in reg:
        f = OUT / (s["id"] + ".json")
        if s.get("disabled"):
            if f.exists():
                f.write_text("[]", encoding="utf-8")
            stats[s["id"]] = dict(n=0, win=0, lo=None, hi=None)
            continue
        if args and s["id"] not in args:
            rows = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        else:
            rows = collect(s)
            if rows is None:
                print("%-14s 확인 불가 (조회 실패)" % s["id"])
                rows = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
            else:
                f.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
                ys = sorted({r["year"] for r in rows})
                smp = [r for r in rows if r["year"] == (ys[-3] if len(ys) > 2 else 0)][:2]
                print("%-14s %4d건 (수상 %3d) %s~%s | %s" % (
                    s["id"], len(rows), sum(1 for r in rows if r["result"] == "win"), ys[0] if ys else "-",
                    ys[-1] if ys else "-", " ; ".join("%s%s / %s" % ("★" if r["result"] == "win" else "", r["title"][:22], r["author"][:16]) for r in smp)))
        ys = sorted({r["year"] for r in rows})
        stats[s["id"]] = dict(n=len(rows), win=sum(1 for r in rows if r["result"] == "win"),
                              lo=ys[0] if ys else None, hi=ys[-1] if ys else None)
    write_doc(reg, stats)
    print("docs/SOURCES.md 갱신: 소스 %d개, 항목 %d건" % (len(reg), sum(v["n"] for v in stats.values())))


if __name__ == "__main__":
    main()
