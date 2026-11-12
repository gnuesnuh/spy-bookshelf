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
    """저자 표기 후보를 '|'로 여러 개 줄 수 있다: "서배스천 맬러비|세바스찬 말라비".
    YES24 검색은 표기가 조금만 달라도 0건이라, 음역 후보를 차례로 시도한다."""
    variants = [a.strip() for a in author.split("|") if a.strip()]
    last = (None, "못 찾음")
    for a in variants:
        item, how = _find_korean(original, a)
        if item:
            return item, how
        last = (item, how)
    return last


def _find_korean(original, author):
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
            # 원제가 같아도 다른 책일 수 있다(King of Capital 2002/2010, More Money Than God 2004/2010).
            # 저자 확인은 생략하지 않는다. 예외: 서점 데이터에 저자 이름이 아예 없는 상품만 원제 일치로 받는다.
            ra = i.get("author") or ""
            no_author = not re.search(r"[가-힣A-Za-z]{2,}\s*(공?저|지음|글)", ra)
            if author_ok(author, ra) or (no_author and en(i.get("originalTitle")) in origs):
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
    t = re.sub("[぀-ヿ一-鿿]+", " ", t)   # 제목에 병기된 일본어·한자 원제
    t = re.sub(r"\s*(상\s*,\s*하\s*)?세트\s*$", "", t.strip())
    t = re.sub(r"\s*[-–:]\s.*$", "", t)                 # 부제
    t = re.sub(r"\s*\d+\s*권?\s*$|\s*[상중하]\s*$", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()


# ======================= 일본어 원제 매칭 =======================
# YES24 의 originalTitle 은 일본서에 일본어 표기를 담지만 구자체·기호가 섞인다(惡意, 假面山莊, マスカレ-ド.ライフ).
import unicodedata

_KYU = ("亞亜 惡悪 壓圧 圍囲 爲為 醫医 壹壱 稻稲 飮飲 隱隠 營営 榮栄 衞衛 驛駅 圓円 鹽塩 奧奥 應応 歐欧 毆殴 櫻桜 假仮 價価 畫画 "
        "會会 繪絵 擴拡 殼殻 覺覚 學学 嶽岳 樂楽 勸勧 卷巻 寬寛 歡歓 罐缶 觀観 關関 陷陥 巖巌 顏顔 歸帰 氣気 龜亀 僞偽 戲戯 "
        "犧犠 舊旧 據拠 擧挙 峽峡 挾挟 敎教 狹狭 鄕郷 堯尭 曉暁 區区 驅駆 勳勲 薰薫 徑径 惠恵 溪渓 經経 繼継 莖茎 螢蛍 輕軽 "
        "鷄鶏 藝芸 擊撃 缺欠 儉倹 劍剣 圈圏 檢検 權権 獻献 縣県 險険 顯顕 驗験 嚴厳 廣広 效効 恆恒 鑛鉱 號号 國国 黑黒 濟済 "
        "碎砕 齋斎 劑剤 雜雑 參参 慘惨 棧桟 蠶蚕 贊賛 殘残 絲糸 齒歯 兒児 辭辞 濕湿 實実 舍舎 寫写 釋釈 壽寿 收収 從従 澁渋 "
        "獸獣 縱縦 肅粛 處処 緖緒 敍叙 奬奨 將将 燒焼 稱称 證証 乘乗 剩剰 壤壌 孃嬢 條条 淨浄 疊畳 繩縄 讓譲 釀醸 囑嘱 觸触 "
        "寢寝 愼慎 晉晋 眞真 盡尽 圖図 粹粋 醉酔 隨随 髓髄 數数 樞枢 聲声 靜静 齊斉 攝摂 竊窃 專専 戰戦 淺浅 潛潜 纖繊 踐践 "
        "錢銭 禪禅 雙双 壯壮 搜捜 插挿 爭争 總総 聰聡 莊荘 裝装 騷騒 增増 臟臓 藏蔵 屬属 續続 墮堕 體体 對対 帶帯 滯滞 臺台 "
        "瀧滝 擇択 澤沢 單単 擔担 膽胆 團団 彈弾 斷断 癡痴 遲遅 晝昼 蟲虫 鑄鋳 廳庁 聽聴 鎭鎮 遞逓 鐵鉄 轉転 點点 傳伝 黨党 "
        "盜盗 燈灯 當当 鬪闘 德徳 獨独 讀読 屆届 貳弐 惱悩 腦脳 霸覇 廢廃 拜拝 賣売 麥麦 發発 髮髪 拔抜 蠻蛮 祕秘 濱浜 "
        "甁瓶 佛仏 拂払 竝並 變変 邊辺 辨弁 瓣弁 辯弁 舖舗 寶宝 豐豊 襃褒 沒没 飜翻 槇槙 萬万 滿満 默黙 譯訳 藥薬 與与 餘余 "
        "譽誉 搖揺 樣様 謠謡 遙遥 來来 賴頼 亂乱 覽覧 龍竜 兩両 獵猟 綠緑 壘塁 淚涙 勵励 禮礼 隸隷 靈霊 齡齢 戀恋 爐炉 勞労 "
        "樓楼 郞郎 祿禄 錄録 灣湾 穗穂 俱倶 俠侠 鷗鴎").split()
_OLD2NEW = {p[0]: p[1] for p in _KYU if len(p) == 2}
JA_RE = re.compile("[぀-ヿ一-鿿]")


def is_ja(s):
    return bool(JA_RE.search(s or ""))


def jn(s):
    """일본어 제목 정규화: 전각·반각 통일, 구자체→신자체, 기호·장음·공백 제거."""
    s = unicodedata.normalize("NFKC", s or "")
    s = "".join(_OLD2NEW.get(ch, ch) for ch in s).lower()
    return re.sub("[\\s\\-ー‐―・.,、。!?「」『』()\\[\\]〈〉《》:;~〜/]", "", s)


# --- 가나 → 한글 (외래어 표기법 일본어 표기 기준, 저자명 검색어를 만드는 용도) ---
_K1 = {  # 가나: 한글, 또는 (어두, 어중)
    "あ": "아", "い": "이", "う": "우", "え": "에", "お": "오",
    "か": ("가", "카"), "き": ("기", "키"), "く": ("구", "쿠"), "け": ("게", "케"), "こ": ("고", "코"),
    "さ": "사", "し": "시", "す": "스", "せ": "세", "そ": "소",
    "た": ("다", "타"), "ち": ("지", "치"), "つ": "쓰", "て": ("데", "테"), "と": ("도", "토"),
    "な": "나", "に": "니", "ぬ": "누", "ね": "네", "の": "노",
    "は": "하", "ひ": "히", "ふ": "후", "へ": "헤", "ほ": "호",
    "ま": "마", "み": "미", "む": "무", "め": "메", "も": "모",
    "や": "야", "ゆ": "유", "よ": "요", "ら": "라", "り": "리", "る": "루", "れ": "레", "ろ": "로",
    "わ": "와", "を": "오",
    "が": "가", "ぎ": "기", "ぐ": "구", "げ": "게", "ご": "고", "ざ": "자", "じ": "지", "ず": "즈", "ぜ": "제", "ぞ": "조",
    "だ": "다", "ぢ": "지", "づ": "즈", "で": "데", "ど": "도", "ば": "바", "び": "비", "ぶ": "부", "べ": "베", "ぼ": "보",
    "ぱ": "파", "ぴ": "피", "ぷ": "푸", "ぺ": "페", "ぽ": "포",
}
_K2 = {  # 요음
    "きゃ": ("갸", "캬"), "きゅ": ("규", "큐"), "きょ": ("교", "쿄"), "しゃ": "샤", "しゅ": "슈", "しょ": "쇼",
    "ちゃ": ("자", "차"), "ちゅ": ("주", "추"), "ちょ": ("조", "초"), "にゃ": "냐", "にゅ": "뉴", "にょ": "뇨",
    "ひゃ": "햐", "ひゅ": "휴", "ひょ": "효", "みゃ": "먀", "みゅ": "뮤", "みょ": "묘", "りゃ": "랴", "りゅ": "류", "りょ": "료",
    "ぎゃ": "갸", "ぎゅ": "규", "ぎょ": "교", "じゃ": "자", "じゅ": "주", "じょ": "조", "びゃ": "뱌", "びゅ": "뷰", "びょ": "뵤",
    "ぴゃ": "퍄", "ぴゅ": "퓨", "ぴょ": "표",
}
_O_ROW = set("おこそとのほもよろごぞどぼぽをょ")
_U_ROW = set("うくすつぬふむゆるぐずづぶぷゅ")


def kana_to_hangul(kana):
    """'ちねん みきと' → '치넨 미키토'. 장음(おう·うう·おお)은 적지 않는다."""
    kana = unicodedata.normalize("NFKC", kana or "")
    kana = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in kana)   # 가타카나 → 히라가나
    words = []
    for part in kana.split():
        out, i, prev = [], 0, ""
        while i < len(part):
            two, one = part[i:i + 2], part[i]
            if one == "ん":
                if out:
                    out[-1] = chr(ord(out[-1]) + 4)     # 받침 ㄴ
                i += 1
            elif one == "っ":
                if out:
                    out[-1] = chr(ord(out[-1]) + 19)    # 받침 ㅅ
                i += 1
            elif one == "ー" or (one == "う" and prev and (prev in _O_ROW or prev in _U_ROW)) \
                    or (one == "お" and prev in _O_ROW):
                i += 1                                   # 장음은 표기하지 않는다
            else:
                step = 2 if two in _K2 else 1
                v = _K2[two] if step == 2 else _K1.get(one)
                if v is not None:
                    out.append(v if isinstance(v, str) else v[0 if not out else 1])
                    prev = part[i + step - 1]
                i += step
        if out:
            words.append("".join(out))
    return " ".join(words)


_AUTHORS = None


def _authors_file():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "data" / "sources" / "ja" / "authors.json"


def ja_author_info(names):
    """일본어 위키백과에서 저자의 한국어판 문서명과 이름 읽기(가나)를 얻는다 → {이름: {ko, kana}}.

    결과는 data/sources/ja/authors.json 에 쌓아 두고 다시 묻지 않는다(위키백과는 요청이 몰리면 429 를 준다).
    """
    global _AUTHORS
    f = _authors_file()
    if _AUTHORS is None:
        _AUTHORS = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    names = [n for n in dict.fromkeys(names) if n]
    todo = [n for n in names if n not in _AUTHORS]
    if todo:
        got = _ja_author_fetch(todo)
        if got:
            _AUTHORS.update(got)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(_AUTHORS, ensure_ascii=False, indent=1), encoding="utf-8")
    return {n: _AUTHORS[n] for n in names if n in _AUTHORS}


def _ja_author_fetch(names):
    info = {}
    for i in range(0, len(names), 20):
        chunk = names[i:i + 20]
        raw = _fetch("https://ja.wikipedia.org/w/api.php?format=json&action=query&redirects=1&prop=langlinks%7Cextracts"
                     "&lllang=ko&lllimit=500&exintro=1&explaintext=1&exsentences=1&exlimit=20&titles="
                     + urllib.parse.quote("|".join(chunk)))
        if raw is None:
            continue
        q = json.loads(raw).get("query", {})
        back = {r["to"]: r["from"] for r in q.get("redirects", [])}
        back.update({n["to"]: n["from"] for n in q.get("normalized", [])})
        for p in q.get("pages", {}).values():
            m = re.search("[（(]\\s*([ぁ-ゖァ-ヶー][ぁ-ゖァ-ヶー\\s]*)", p.get("extract") or "")
            ko = (p.get("langlinks") or [{}])[0].get("*")
            name = back.get(p.get("title"), p.get("title"))
            info[name] = dict(ko=re.sub("\\s*\\(.*?\\)", "", ko) if ko else None, kana=m.group(1).strip() if m else None)
    return info


def korean_author_of(item):
    """YES24 저자 필드 '치넨 미키토 저/김은모 역' → '치넨 미키토'."""
    a = re.split("[/,]", item.get("author") or "")[0]
    return re.sub("\\s*(공?저|글|원저|지음)\\s*$", "", a).strip()


_MANUAL_JA = None


def manual_ja():
    """수동 판정표 scripts/ja_titles.json: {"일본어 원제|일본어 저자": "국내 제목"}.

    YES24 에 원제가 비어 있어 자동으로 못 잇는 책(六人の嘘つきな大学生 ↔ 여섯명의 거짓말쟁이 대학생)을
    Claude Code 가 후보를 보고 판정해 적어 둔다. 값이 "" 이면 '국내판 없음'으로 판정한 것.
    """
    global _MANUAL_JA
    if _MANUAL_JA is None:
        from pathlib import Path
        f = Path(__file__).resolve().parent / "ja_titles.json"
        _MANUAL_JA = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return _MANUAL_JA


def ja_candidates(author_ja, author_info=None):
    """원제가 비어 있는 같은 저자의 국내 출간작 — 수동 판정용 후보."""
    info = (author_info or {}).get(author_ja) or {}
    names = [n for n in dict.fromkeys([info.get("ko"), kana_to_hangul(info.get("kana") or "")]) if n]
    out = {}
    for n in names:
        for i in search(n, 2) or []:
            if not jn(i.get("originalTitle")) and author_ok(n, i.get("author")) and "역" in (i.get("author") or "") \
                    and not any(w in i["title"] for w in SKIP):
                out[base_title(i["title"])] = i.get("publishDate")
    return sorted(out)


def find_korean_ja(title, author_ja, author_info=None):
    """일본어 원제+저자 → (국내판 YES24 상품 또는 None, 근거, 한국어 저자명 후보).

    검색 순서: 일본어 원제 직접 검색 → 저자 한국어 문서명 → 저자 가나를 한글로 옮긴 이름.
    어느 경로든 originalTitle 이 원제와 맞아야 인정한다.
    """
    info = (author_info or {}).get(author_ja) or ja_author_info([author_ja]).get(author_ja) or {}
    ko_names = [n for n in dict.fromkeys([info.get("ko"), kana_to_hangul(info.get("kana") or "")]) if n]
    t = jn(title)
    t_main = jn(title.strip().split()[0]) if title.strip() else ""     # 부제 앞의 본 제목
    seen, failed = {}, False
    for q, pages in [(title, 1)] + [(n, 2) for n in ko_names]:
        rows = search(q, pages)
        if rows is None:
            failed = True
            continue
        for i in rows:
            o = jn(i.get("originalTitle"))
            if not o:
                continue
            ok = (o == t or (len(t_main) >= 3 and o == t_main)
                  or (min(len(o), len(t)) >= 4 and (o in t or t in o))
                  or (len(t) >= 5 and difflib.SequenceMatcher(None, o, t).ratio() >= 0.8))
            if ok:
                seen[i["itemId"]] = i
        if seen:
            break

    def rank(i):
        tt = i.get("title") or ""
        vol = re.search("(\\d+)\\s*권?\\s*$", tt)
        return (not any(w in tt for w in SKIP), "역" in (i.get("author") or ""), "판매중" in (i.get("itemStatus") or ""),
                -int(vol.group(1)) if vol else 0, i.get("salePoint") or 0)

    if seen:
        best = max(seen.values(), key=rank)
        return best, "원제 일치", korean_author_of(best)
    kt = manual_ja().get(title + "|" + author_ja)
    if kt:   # 수동 판정된 국내 제목으로 찾는다
        rows = [i for n in ko_names + [kt] for i in (search(kt if n == kt else n + " " + kt, 1) or [])
                if norm_ko(kt) in norm_ko(i.get("title")) and "역" in (i.get("author") or "")
                and any(author_ok(n2, i.get("author")) for n2 in ko_names)]   # 같은 제목의 다른 저자 책은 제외
        if rows:
            best = max(rows, key=rank)
            return best, "수동 검수", korean_author_of(best)
    return None, ("확인 불가" if failed else "못 찾음"), (ko_names[0] if ko_names else None)


def norm_ko(s):
    return re.sub("[^0-9a-z가-힣]", "", (s or "").lower())
