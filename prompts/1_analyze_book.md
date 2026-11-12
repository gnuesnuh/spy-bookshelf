# 고정 프롬프트 1 — 도서 성격 분석 (PLAYBOOK 단계 0)

Claude Code는 이 프롬프트를 **그대로** 따른다. 즉흥으로 축을 정하지 않는다.

## 입력 (먼저 모은다)
1. `python scripts/yes24_lookup.py "<제목>"` → 한국어 제목, 원제, 원저자, 출판사 소개
2. WebSearch `"<원제>" <원저자> review` → 서평 2~3개를 WebFetch로 읽는다(언론 서평 우선, Goodreads·Amazon 독자평 1개)

## 지시
아래 4개 축을 **모두** 채운다. 각 축은 이 책에 대해 사실인 것만 쓴다.
- `소재`: 무엇을 다루나 (사건·대상·분야 — 명사)
- `주제`: 무엇을 말하나 (책이 독자에게 남기려는 생각 — 소재와 다른 층위여야 한다. 소재를 반복하면 다시 쓴다)
- `형식`: 어떻게 썼나 (체험기·취재 내러티브·학술 교양·회고록·에세이·실용서·소설 등)
- `톤`: 읽는 느낌 (긴장감·성찰적·유머·냉소·따뜻함 등)

축마다:
- `label`: 2~6글자 한국어 이름 (예: "의사결정")
- `desc`: 이 책에서 그 축이 무엇인지 한 줄
- `direction`: 이 축으로 고르면 어떤 책들이 나오는지 한 줄
- `examples`: 그 방향의 대표 원서 2권 (원제, 원저자) — 실재하는 책만
- `search_terms`: 영어 검색어 2~4개 (소스 수집에 그대로 쓴다)

`default`: 서평에서 가장 많이 강조된 축 하나와 근거(어느 서평이 무엇을 강조했나).

## 출력: `data/queries/<slug>.axes.json`
```json
{
 "seed": {"title": "블러프", "original": "The Biggest Bluff", "author_orig": "Maria Konnikova"},
 "reviews_read": ["https://...", "https://..."],
 "axes": [
  {"axis": "소재", "label": "포커", "desc": "...", "direction": "...",
   "examples": [["The Biggest Game in Town", "Al Alvarez"], ["Positively Fifth Street", "James McManus"]],
   "search_terms": ["poker nonfiction books", "best poker memoirs"]},
  {"axis": "주제", ...}, {"axis": "형식", ...}, {"axis": "톤", ...}
 ],
 "default": {"axis": "주제", "why": "NYT·Guardian 서평 모두 '불확실성 속 판단'을 중심으로 소개"},
 "chosen": null
}
```

## 사용자 확인
AskUserQuestion 한 번, multiSelect=true. 선택지 = 4개 축 각각 `"[축] label — direction"`, 기본 축에 "(추천)".
사용자가 고른 축(들)을 `chosen: ["주제"]`로 저장한다. 사용자가 이미 의도를 말했거나 자리에 없으면 묻지 않고 `chosen: [default]`, `"chosen_by": "default"`.
