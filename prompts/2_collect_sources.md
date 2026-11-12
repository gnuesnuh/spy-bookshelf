# 고정 프롬프트 2 — 소스 수집 (PLAYBOOK 단계 2)

## 순서
1. `python scripts/plan_sources.py <slug>` → `<slug>.plan.json` (실행할 검색·스크립트 목록). 이 목록을 **전부** 실행한다. 빼면 이유를 plan.json의 해당 항목 `skipped`에 적는다.
2. 웹 검색 항목: WebSearch → 결과 중 **책 목록이 있는 페이지 1~2개**를 WebFetch로 연다. 열어서 읽은 페이지만 근거다.
3. 읽은 페이지마다 `data/sources/web/<slug>.json`에 한 항목을 추가한다(아래 형식). 페이지에 나온 책을 **빠짐없이** 원제·원저자로 옮긴다(축에 맞는지는 여기서 거르지 않는다 — 거르는 건 단계 4).
4. 스크립트 항목(award_candidates, community_fetch, gemini_candidates)은 그대로 실행한다. 결과 파일은 `aggregate.py`가 직접 읽는다.

## 근거 파일 형식 `data/sources/web/<slug>.json`
```json
[
 {"source": "Five Books — Annie Duke on Decision Making",
  "kind": "expert",
  "url": "https://fivebooks.com/best-books/...",
  "for_axis": "주제",
  "read_at": "2026-11-13",
  "books": [["Thinking, Fast and Slow", "Daniel Kahneman"], ["The Signal and the Noise", "Nate Silver"]]}
]
```
- `kind`: `expert`(전문가·저자 추천: Five Books, Shepherd, 저자 인터뷰) · `press`(언론 서평·결산: NYT, Guardian, Economist, FT) · `list`(독자 목록: Goodreads list) · `award`(웹에서 직접 읽은 수상 목록) · `community`(포럼 글)
- `source`는 사람이 읽을 이름. 같은 사이트라도 페이지(추천인)가 다르면 다른 소스다.
- 책 원제는 페이지에 적힌 대로. 모르면 비우지 말고 페이지 표기 그대로 적는다(집계가 정규화한다).
