# REQ-002 추천 목록 작성 절차 공유

- 상태: 답변 완료 (시험 4번은 사용자 확인 대기)
- 요청: 채팅(클라우드) 세션, 2026-11-13
- 처리: 로컬 Claude Code

## 배경
사용자 말: "클로드코드 쪽은 책 제목만 가지고 리스팅하는 로직을 전혀 못 따라간다."
채팅 세션이 why-fish·barbarians·bluff 목록을 만든 방법이 문서로 없었다. 이를 `docs/PLAYBOOK.md`에 적었다.
또 사용자와 새로 정한 두 가지를 `docs/PLAN.md` 6절에 반영했다.
1. **단계 0 도서 성격 분석 + 의도 확인** (소재·주제·형식·톤 → 객관식 질문)
2. **단계 확장 규칙** (1순위 고른 축 → 2순위 다른 축 → 3순위 저자·형식 → 4순위 국내서, 국내판 10권까지)

## 요청
1. `docs/PLAYBOOK.md`와 PLAN 6절을 읽는다.
2. 로컬 도구와 어긋나는 곳을 고친다(문서든 코드든). 특히 확인할 것:
   - `award_candidates.py`의 출력이 PLAYBOOK 3·4절 집계에 그대로 들어가는지
   - 카테고리의 `[N순위]` 표기를 `build_query.py`·웹앱이 문제없이 보여 주는지(필요하면 순위 필드를 따로 두자고 제안)
   - '국내판 10권 미만이면 확장' 판단을 `build_query.py` 끝에 출력해 줄 수 있는지(국내판 있는 책 수 한 줄)
3. 이해가 안 되거나 다르게 해야 할 이유가 있으면 아래 '답변'에 적는다. 채팅 세션이 다음에 읽는다.
4. 시험(선택): 『블러프』를 '주제: 의사결정' 축으로 PLAYBOOK대로 다시 만들어 기존 `bluff`와 비교(slug 예: `bluff-decision`).

## 답변 (로컬 Claude Code, 2026-11-13)
`docs/PLAYBOOK.md`와 PLAN 6절을 읽었다. 그동안 로컬 세션은 PLAYBOOK의 0번 원칙("목록은 스크립트가 만들지 않는다")과 반대로, 소스 캐시만으로 목록을 만들었다. 그 목록들은 삭제했고(PROGRESS 11절) 앞으로는 PLAYBOOK을 따른다.

### 확인 요청 3건
1. **`award_candidates.py` 출력 → PLAYBOOK 3·4절 집계**: 들어간다. `data/queries/<slug>.awards.json`의 `candidates[]`가 책마다 `original`(원제), `author_orig`(원저자), `awards`("Edgar Award 2018 수상 · Gold Dagger 2018 후보" 식 문자열), `score`를 준다.
   - 집계할 때 **어워드 소스 하나하나를 근거 1곳으로** 세면 된다(`awards`를 ` · `로 나누면 된다). 다만 종류는 전부 '어워드' 1종류다.
   - `category`의 "같은 해 함께 오른 작품 / 같은 작가 / 비슷한 시기 상위작"은 어워드 안에서의 관계일 뿐, 축 판단이 아니다. 축에 맞는지는 Claude Code가 본다.
   - 한계: 기준 도서가 어워드에 오른 적이 없으면 `--seed`가 실패한다(The Biggest Bluff가 그랬다). 그때는 `--genre nonfiction|business|science|history|mystery|sf|literary`.
   - 후보의 `title`·`author`(한글)는 스크립트가 YES24에서 찾은 값이다. 목록에는 PLAYBOOK대로 한국어 제목을 비우고 원제·저자만 옮긴다.
2. **`[N순위]` 표기**: 순위 필드를 따로 뒀다. `build_query.py`가 카테고리 앞의 `[1순위]`를 떼어 `tier: 1`로 저장하고, 웹앱은 카드에 "1순위 · 판단·확률"로 보여 준다. 목록 파일에는 지금처럼 `"[1순위] 판단·확률"`로 적으면 된다(사전 형식이면 `tier`를 직접 줘도 된다).
   - "미번역은 스크립트가 '미번역 명작'으로 분리한다"는 실제로는 구현돼 있지 않았다. 이번에 넣었다: 국내판 판정이 '없음'이면 `category`를 "미번역 명작"으로 바꾸고 원래 갈래는 `group`에 남긴다. 국내서(원제 `-`)는 제외.
3. **국내판 10권 미만이면 확장**: `build_query.py` 끝에 출력한다. 예(barbarians): `국내판 있는 책 17권 (목표 10권) · 그중 전자책·구독 가능 5권 · 미번역 8권` / `→ 목표 충족: 확장하지 않는다.` 순위가 있으면 순위별 국내판 수도 나온다. 목표는 `--target N`으로 바꾼다.

### 로컬에서 추가로 고친 것 (목록 작성 흐름에 영향)
- 저자 표기 변형 `A|B`: 서점 제목 대조(`is_match`)가 변형을 하나씩 본다. 웹앱은 첫 번째 표기만 보여 준다.
- `build_query.py`가 국내 정보 뒤에 리뷰 수집까지 한다. Goodreads가 3권 연속 응답하지 않으면 건너뛰고, 그 책은 "수집 보류"로 표시된다(리뷰 없음과 구분). 빼려면 `--no-reviews`.
- 이전 결과 재사용 조건은 그대로(원제·저자가 같으면 재사용).

### 다르게 했으면 하는 점 / 질문
- PLAYBOOK 3절 표의 Shepherd·Five Books·언론 목록은 매번 웹 검색으로 찾는다. 같은 기준 도서나 같은 주제가 다시 나오면 다시 읽게 되므로, **읽은 페이지 URL과 거기 나온 책을 `data/sources/web/<slug>.json` 같은 곳에 남기자**고 제안한다(PLAYBOOK 3절의 "메모해 둔다"를 파일로). 형식은 소스 캐시와 같게 `{source, url, title, author}`.
- PLAYBOOK 4절 집계(`<slug>.rank.json`)는 아직 수작업이다. 위 메모 파일 + `awards.json` + `community/*.json` + `*.gemini.json`을 읽어 원제 기준으로 묶고 근거 수를 세는 스크립트를 로컬에서 만들 수 있다. 만들지 여부는 사용자와 정한다.
- 단계 0의 객관식 질문은 로컬 세션에서도 AskUserQuestion으로 한다.

### 시험 4번 (bluff-decision) — 완료 (2026-11-13)
사용자 확인 후 PLAYBOOK 순서대로 만들었다. 축은 요청서대로 '주제: 의사결정'으로 두고 묻지 않았다. (사용자 메모: 단계 0의 객관식 질문은 이번에 새로 정한 절차이고, 지금까지 실제로 물어본 적은 없다.)
- 읽은 페이지(직접 열어 확인): Five Books 3건(Sebastian Park · Jonah Lehrer 의사결정 · Edouard Mathieu 데이터), Farnam Street 의사결정 심리 목록, Time(Re:Think Decision Making 참가자 추천), Alliance for Decision Education 추천 도서, Annie Duke 블로그(본문 3권만 읽힘). URL은 `data/sources/web/bluff-decision.json`.
- 못 연 것: Shepherd·bookdna·thegreatestbooks는 WebFetch 403, 로컬 요청으로는 Shepherd 본문이 스크립트 렌더링이라 책 목록이 안 나왔다. 2순위 포커 책의 Shepherd·Five Books(Coren)·Nolan Dalla 근거는 기존 `bluff` 목록의 것을 그대로 썼다.
- 커뮤니티: `community_fetch.py bluff-decision`(의사결정 검색어 4개) 428건 — 이 축에서는 언급이 얇았다(Thinking in Bets 2스레드 등). 기존 `bluff.json`의 HN 언급과 합쳐 '커뮤니티(HN)' 1곳으로 셌다. Gemini는 새로 부르지 않고 기존 `bluff.gemini.json`을 썼다.
- 어워드: 소스 캐시에서 후보 제목을 직접 대조(The Black Swan·Misbehaving = FT 경영서 명단, The Drunkard's Walk·Moonwalking with Einstein = Royal Society 후보). `ft_business`는 수상/후보 구분이 안 읽혀 '명단'으로만 적었다.
- 집계: `data/queries/bluff-decision.rank.json`. 목록 25권 = 기준 1 + 1순위 18(판단·확률) + 2순위 5(포커 논픽션 4, 심리 도전기 1) + 3순위 1(같은 저자).
- 결과: 국내판 19권(1순위 17/18), 전자책·구독 가능 13권, 미번역 5권 → 목표 충족, 4순위(국내서)까지 내려가지 않았다. 국내판 19권 모두 YES24 원제 일치.
- 기존 `bluff`와 비교: `bluff`는 포커 책이 12권(실전서 포함)이고 국내판 13권·전자책 8권. `bluff-decision`은 포커 책 4권, 국내판 19권·전자책 13권. 겹치는 책은 기준 도서 포함 14권.
- 하면서 걸린 것
  - How to Measure Anything은 YES24에 원제가 같은 다른 저자 책(『측정의 과학』)이 있었다. 저자 대조로 걸러져 '국내판 없음'이 됐다.
  - 리뷰 요약 재사용이 원제 표기 차이(Superforecasting ↔ Superforecasting: The Art…)와 동시 조회 경합 때문에 안 됐다 → 고쳤다(`build_data._work_key`).
  - 영상화는 위키데이터 요청 제한(429)으로 이번에도 못 붙였다.
