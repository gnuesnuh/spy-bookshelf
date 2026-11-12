"""원제 + 한글 저자명으로 YES24에서 국내판(번역본)을 찾는 공용 모듈.

eval_sheet.py 에 있던 find_korean 을 옮겨 온 것. build_data.py(웹앱 데이터), build_query.py(추천 목록),
eval_sheet.py(채점)가 함께 쓴다. 규칙은 CLAUDE.md '번역본 매칭 규칙' 참고.

쓰기 전에 configure(fetch, yes24_key) 로 조회 함수를 넘겨야 한다(build_data 와의 순환 import 를 피하려는 것).
"""
import difflib
import json
import re
import urllib.parse

_fetch = None
_key = None


def configure(fetch, key):
    global _fetch, _key
    _fetch, _key = fetch, key


NUM = dict(one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10, eleven=11, twelve=12,
           thirteen=13, twenty=20, thirty=30, forty=40, fifty=50)


def words2num(s):  # "Thirty-Nine Steps" -> "39 Steps"
    def rep(m):
        a, b = m.group(1).lower(), (m.group(2) or "").lower()
        return str(NUM[a] + NUM.get(b, 0))
    keys = "|".join(sorted(NUM, key=len, reverse=True))
    return re.sub(r"\b(%s)(?:[-\s](%s))?\b" % (keys, keys), rep, s, flags=re.I)


def en(s):
    s = words2num(s or "")
    s = re.sub(r"\(.*?\)|\b(series|trilogy|the|a|an)\b", " ", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def search(q, pages=1, category="BOOK"):
    """YES24 검색. 조회 실패는 None(확인 불가), 결과 없음은 []."""
    if not _key:
        return None
    out = []
    for pg in range(1, pages + 1):
        raw = _fetch("https://apis.yes24.com/v1/goods/itemList?category=%s&detail=Y&pageSize=100&page=%d&query="
                     % (category, pg) + urllib.parse.quote(q), headers={"X-Api-Key": _key})
        if raw is None:
            return None if not out else out
        try:
            items = (json.loads(raw).get("data") or {}).get("items") or []
        except ValueError:
            items = []
        out += items
        if len(items) < 100:
            break
    return out


def item_detail(item_id):
    """상품 번호로 상세 조회. 없는 상품이면 {}, 조회 실패면 None."""
    if not _key:
        return None
    raw = _fetch("https://apis.yes24.com/v1/goods/itemDetail?searchType=ItemId&detail=Y&query=%s" % item_id,
                 headers={"X-Api-Key": _key})
    if raw is None:
        return None
    try:
        data = json.loads(raw).get("data") or {}
    except ValueError:
        return None
    it = data.get("item") or data.get("items") or data
    if isinstance(it, list):
        it = it[0] if it else {}
    return it if isinstance(it, dict) and it.get("itemId") else {}


# --- 한글 → 로마자 골격 (원제 필드가 빈 책을 음역으로 대조하기 위한 간이 변환) ---
CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
JUNG = ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi", "yu",
        "eu", "ui", "i"]
JONG = ["", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l", "m", "p", "p", "t", "t", "ng",
        "t", "t", "k", "t", "p", "t"]


def roman(s):
    out = []
    for ch in s or "":
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            out.append(CHO[c // 588] + JUNG[(c % 588) // 28] + JONG[c % 28])
        elif ch.isascii() and ch.isalnum():
            out.append(ch.lower())
    return "".join(out)


def skel(s):  # 자음 골격: 음역 표기 흔들림(f/p, v/b, l/r, th/s)을 흡수
    s = (s.lower().replace("ph", "p").replace("th", "s").replace("f", "p").replace("v", "b").replace("l", "r")
         .replace("z", "s").replace("j", "s").replace("x", "ks").replace("c", "k").replace("q", "k").replace("w", ""))
    return re.sub(r"[^bcdghjkmnprst]", "", s)


def author_ok(author, r_author):
    """저자 표기 흔들림 허용: 성(마지막 토큰)의 음역 골격 비교. 헤론↔헤런, 카레이루↔캐리루."""
    a = skel(roman(author.split()[-1]))
    for name in re.split(r"[,/]", r_author or ""):
        name = re.sub(r"\s*(공?저|역|글|그림|편|원저|감수|지음|옮김)\b.*", "", name).strip()
        if not name:
            continue
        b = skel(roman(name.split()[-1]))
        if a and b and difflib.SequenceMatcher(None, a, b).ratio() >= 0.7:
            return True
    return False


SKIP = ("큰글자", "세트", "청소년", "어린이")


def find_korean(original, author):
    """원제+저자 → (국내판 YES24 상품 dict 또는 None, 근거).

    근거: "원제 일치"(확정 ✅) / "음역 일치"(유력 ⚠️) / "못 찾음" / "확인 불가"(조회 실패).
    """
    o1 = original.split("/")[0].split("(")[0].strip()
    origs = [en(o) for o in original.split("/") if en(o)]
    last = author.split()[-1]
    seen, failed = {}, False
    for q, pages in [(author, 3), (last, 2), (last + " " + o1, 1), (o1, 1)]:
        rows = search(q, pages)
        if rows is None:
            failed = True
            continue
        for i in rows:
            if author_ok(author, i.get("author")) or "역" in (i.get("author") or "") and en(i.get("originalTitle")) in origs:
                seen[i["itemId"]] = i
        # 원제가 정확히 같은 국내판이 나왔으면 남은 검색은 하지 않는다(조회 시간 단축)
        if any(en(i.get("originalTitle")) in origs for i in seen.values()):
            break

    def rank(i):  # 같은 점수면 본판·판매중·판매지수 높은 쪽
        t = i.get("title") or ""
        vol = re.search(r"(\d+)\s*권?\s*$", t)   # 분권이면 1권을 대표로
        return (not any(w in t for w in SKIP), "판매중" in (i.get("itemStatus") or ""),
                -int(vol.group(1)) if vol else 0, i.get("salePoint") or 0)

    best, score = None, 0.0
    for i in seen.values():
        ot = en(i.get("originalTitle"))
        if not ot:
            continue
        s = max((1.0 if o == ot or (min(len(o), len(ot)) >= 10 and (o in ot or ot in o))
                 else difflib.SequenceMatcher(None, o, ot).ratio()) for o in origs)
        if s > score or (s == score and best is not None and rank(i) > rank(best)):
            best, score = i, s
    if best and score >= 0.75:
        return best, "원제 일치"
    # 원제 필드가 빈 책: 국내 제목의 음역 골격과 원제 골격 비교 (퍼핏 쇼 ↔ Puppet Show)
    best, score = None, 0.0
    for i in seen.values():
        if en(i.get("originalTitle")) or not author_ok(author, i.get("author")) or last in i["title"]:
            continue  # 제목에 저자 이름이 든 책(『이그나티우스의 편지』)은 음역 대조에서 뺀다
        t = skel(roman(re.sub(r"\(.*?\)|\d+$", "", i["title"])))
        for o in original.split("/"):
            oo = skel(re.sub(r"\(.*?\)|\b(the|a|an|series|trilogy)\b", " ", o.lower()))
            if len(t) >= 3 and len(oo) >= 3:
                r = difflib.SequenceMatcher(None, t, oo).ratio()
                if r > score:
                    best, score = i, r
    if best and score >= 0.7:
        return best, "음역 일치"
    return None, ("확인 불가" if failed and not seen else "못 찾음")


def base_title(title):
    """『자칼의 날 1』 『나이트 매니저(The Night Manager) 02권』 → 서점 검색용 본 제목."""
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", title or "")
    t = re.sub(r"\s*[-–:]\s.*$", "", t)                 # 부제
    t = re.sub(r"\s*\d+\s*권?\s*$|\s*[상중하]\s*$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()
