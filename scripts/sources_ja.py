"""일본 어워드·랭킹을 일본어 위키백과에서 받아 data/sources/ja/<소스>.json 으로 저장한다 (소스 캐시).

사용법:  python scripts/sources_ja.py            (캐시 사용)
        python scripts/sources_ja.py --refresh  (위키백과에서 다시 받기)

소스 (국내 작품 부문만)
  konomys  このミステリーがすごい!  연도별 국내편 1~10위
  bunshun  週刊文春ミステリーベスト10  연도별 국내부문 1~10위
  honya    本屋大賞  연도별 1~10위
항목 형식: {source, year, rank, title, author}  — 제목·저자는 일본어 표기 그대로.
수상 결과는 바뀌지 않으므로 한 번 받으면 다시 받을 필요가 없다. 새 연도가 추가됐을 때만 --refresh.
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_data import DATA, fetch  # noqa: E402

OUT = DATA / "sources" / "ja"
PAGES = {"konomys": "このミステリーがすごい!", "bunshun": "週刊文春ミステリーベスト10", "honya": "本屋大賞"}
LABEL = {"konomys": "このミステリーがすごい!", "bunshun": "週刊文春ミステリーベスト10", "honya": "本屋大賞"}


def wikitext(page):
    raw = fetch("https://ja.wikipedia.org/w/api.php?format=json&action=parse&prop=wikitext&redirects=1&page="
                + urllib.parse.quote(page))
    return json.loads(raw)["parse"]["wikitext"]["*"] if raw else None


def plain(s):
    s = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)      # [[링크|표시]] → 표시
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"'''?|<[^>]+>", "", s)
    return s.strip()


def by_year(text):
    """'== 2021年 ==' 식 제목으로 나눠 (연도, 본문) 목록을 만든다."""
    parts = re.split(r"^=+\s*(\d{4})年[^=\n]*=+\s*$", text, flags=re.M)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def parse_ranked_lists(text, source):
    """このミス·文春 형식: '国内' 표제 아래 '# 제목（저자）' 줄."""
    out = []
    for year, body in by_year(text):
        m = re.search(r"国内[編部門]*.*?\n(.*?)(?=\n\s*\||\n[;']*\s*'*海外|\Z)", body, flags=re.S)
        if not m:
            continue
        rank = 0
        for line in m.group(1).splitlines():
            if not line.startswith("#"):
                continue
            rank += 1
            for piece in re.split(r"<br\s*/?>", line.lstrip("#").strip()):   # 공동 순위는 <br>로 나열된다
                mm = re.match(r"(.+)[（(]([^（()）]+)[)）]\s*$", plain(piece))
                if mm and rank <= 10:
                    out.append(dict(source=source, year=year, rank=rank, title=mm.group(1).strip(),
                                    author=mm.group(2).strip()))
    return out


def parse_honya(text):
    """本屋大賞 형식: 연도별 wikitable. '本屋大賞' 부문 행만 쓴다(翻訳小説·発掘 부문 제외)."""
    out = []
    for year, body in by_year(text):
        part = None
        for row in body.split("\n|-"):
            head = row.split("{{Center")[0]
            if "翻訳小説" in head or "発掘" in head or "ノンフィクション" in head or "超発掘" in head:
                part = "other"
            elif "本屋大賞" in head:
                part = "honya"
            m = re.search(r"\{\{Center\|(\d+)\}\}\s*\|\|(.*?)\|\|(.*?)(?:\|\||\n|$)", row, flags=re.S)
            if m and part == "honya" and int(m.group(1)) <= 10:
                title, author = plain(m.group(2)), plain(m.group(3))
                if title and author:
                    out.append(dict(source="honya", year=year, rank=int(m.group(1)), title=title, author=author))
    return out


def load_all():
    """저장된 소스를 모두 읽는다. 없으면 빈 목록."""
    rows = []
    for name in PAGES:
        f = OUT / (name + ".json")
        if f.exists():
            rows += json.loads(f.read_text(encoding="utf-8"))
    return rows


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, page in PAGES.items():
        text = wikitext(page)
        if text is None:
            print(name, "확인 불가 (위키백과 조회 실패)")
            continue
        rows = parse_honya(text) if name == "honya" else parse_ranked_lists(text, name)
        (OUT / (name + ".json")).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        years = sorted({r["year"] for r in rows})
        print("%s: %d건, %s~%s년 (%d개 연도)" % (name, len(rows), years[0] if years else "-", years[-1] if years else "-", len(years)))
        for r in [x for x in rows if x["year"] == (years[-2] if len(years) > 1 else 0)][:3]:
            print("   ", r["year"], r["rank"], r["title"], "/", r["author"])


if __name__ == "__main__":
    main()
