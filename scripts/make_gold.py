"""시트(정답 후보) + 실제 조회 결과 → 검수된 정답지 data/gold.json.

판정
  verified        원제 일치로 국내판 확인
  verified_alias  국내판은 있으나 시트의 한국어 제목이 틀림 → 실제 제목으로 교정
  untranslated    시트·조회 모두 미번역
  suspect         시트는 '번역됨'이나 저자의 국내 출간 목록 어디에도 없음 (시트 오류 의심)
  unverifiable    국내판이 있을 수 있으나 데이터 한계로 확인 불가
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ev = {r["id"]: r for r in json.loads((ROOT / "data/cache/eval_translation.part.json").read_text(encoding="utf-8"))}
books = json.loads((ROOT / "data/books.json").read_text(encoding="utf-8"))["books"]

# 사람 검수가 들어간 판정 (근거 = 2026-11-13 YES24 Open API 저자별 국내 출간 목록 + 밀리·리디·크레마 자동 조회)
MANUAL = {
    "여행자": ("verified_alias", "아이 앰 필그림", "테리 헤이스 저, 원제 필드 비어 있음. 시트 제목 '여행자'는 오류"),
    "안드로메다 스트레인": ("verified_alias", "안드로메다 스트레인", "YES24 상품의 저자 필드가 비어 있어 자동 매칭 실패"),
    "시부미": ("suspect", None, "트레바니안 국내 출간작은 『아이거 빙벽』뿐"),
    "가브리엘 알론 시리즈": ("suspect", None, "대니얼 실바 국내 출간작 검색 결과 없음"),
    "에이전트 지그재그 / 민스미트 작전": ("suspect", None, "벤 매킨타이어 국내 출간작은 『스파이와 배신자』『콜디츠』뿐"),
    "억만 달러 스파이": ("suspect", None, "데이비드 호프만 국내 출간작은 『데드핸드』뿐"),
    "장교와 스파이": ("suspect", None, "로버트 해리스 국내 출간 16종에 없음"),
    "뮌헨": ("suspect", None, "로버트 해리스 국내 출간 16종에 없음"),
    "열한 번째 계명": ("suspect", None, "제프리 아처 국내 출간 7종에 없음"),
    "데드 그라운드": ("suspect", None, "M.W. 크레이븐 국내 출간작은 퍼핏 쇼·블랙 서머·큐레이터 3종뿐"),
    "보타니스트": ("suspect", None, "M.W. 크레이븐 국내 출간작은 퍼핏 쇼·블랙 서머·큐레이터 3종뿐"),
    "고통의 제국": ("suspect", None, "패트릭 라든 키프 국내 출간작은 『세이 나씽』뿐"),
    "크렘린의 추기경": ("unverifiable", None, "톰 클랜시 검색 결과가 40건 상한에서 세트 상품으로 채워짐. 구판·절판 가능"),
    "붉은 10월": ("unverifiable", None, "톰 클랜시 검색 결과 40건 상한. 구판·절판 가능"),
    "패트리어트 게임": ("unverifiable", None, "톰 클랜시 검색 결과 40건 상한. 구판·절판 가능"),
}

gold = []
for b in books:
    e = ev.get(b["id"], {})
    sheet_tr = "미번역" not in b["note"]
    if b["title"] in MANUAL:
        verdict, title, why = MANUAL[b["title"]]
    elif e.get("found"):
        same = e.get("same_title")
        verdict, title = ("verified" if same else "verified_alias"), e["found"]
        why = f"원제 일치: {e.get('found_original') or '음역 일치'}"
    elif not sheet_tr:
        verdict, title, why = "untranslated", None, "시트·조회 모두 국내판 없음"
    else:
        verdict, title, why = "unverifiable", None, "자동 매칭 실패"
    st = b["stores"]
    gold.append(dict(id=b["id"], list=b["list"], category=b["category"], original=b["original"], author=b["author"],
                     sheet_title=b["title"], korean_title=title, verdict=verdict, evidence=why,
                     stores=dict(millie=st["millie"]["status"], ridi=st["ridi"]["status"], crema=st["crema"]["status"]),
                     sheet_stores=b["sheet"]))
(ROOT / "data/gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
print(Counter(g["verdict"] for g in gold))
for v in ("verified_alias", "suspect", "unverifiable"):
    print(v, [f"{g['sheet_title']}→{g['korean_title'] or '-'}" for g in gold if g["verdict"] == v])
