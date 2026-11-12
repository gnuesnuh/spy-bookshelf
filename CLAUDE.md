# Books — 도서 추천 · 국내 번역본 · 전자책 입점 확인 서비스

장르나 책 제목을 넣으면 추천 목록을 만들고, 각 책의 국내 번역본과 전자책·구독 서비스 입점 여부를 붙인다.
기획(목표·범위·작업 절차·로드맵)은 `docs/PLAN.md`, 진행 이력과 검증 수치는 `docs/PROGRESS.md`. 작업 전에 둘 다 읽을 것.
추천 요청을 받으면 `docs/PLAN.md` 6절 '사용 흐름'을 따른다.

## 열린 요청
`docs/requests/`의 상태 '대기' 요청서를 먼저 확인한다. 로컬 PC에서 실행 중이면 처리하고 결과를 요청서에 기록한다.
- REQ-001 Reddit 추천 스레드 수집 (로컬 실행 필요)

## 출력 기준 (정답 형식)
기존 Google 시트(ID `10hYwTqAXoqn-qZ3u1YCN4RVWBhYQGTcBXctbljjc9mQ`, 로컬 사본 `data/sheet.xlsx`)와 같은 열 구성:
카테고리 · 한국어 제목 · 원제 · 저자 · 수상 및 선정 이력 · 영미권/국내 평점 · 리뷰 요약 및 추천 포인트 ·
YES24 eBook · 밀리의서재 · 리디셀렉트 · 크레마클럽 · 비고.
단, 시트 자체에 오류가 있다(제목 오기, 미번역 도서를 '번역됨'으로 표기, 리디셀렉트 과다 표기).
**채점용 정답지는 시트가 아니라 검수본 `data/gold.json`을 쓴다.**

## 데이터 소스 (2026-11-13 기준)
| 소스 | 상태 | 용도 |
|---|---|---|
| YES24 Open API `apis.yes24.com/v1/goods/itemList` | 사용 중. 키는 `.env`의 `YES24_API_KEY` (헤더 `X-Api-Key`) | 원제(`originalTitle`), 판매상태, 평점(`starScore`), 판매지수, 연결 eBook(`eBookLink`, detail=Y) |
| 밀리의서재 `live-api.millie.co.kr` 검색 | 사용 중 (build_data.py) | 입점 여부 |
| 리디 `search-api.ridibooks.com` | 사용 중 (build_data.py, 브라우저 UA 필요) | 셀렉트/단권 |
| 크레마클럽 `cremaclub.yes24.com` 검색 페이지 | 사용 중 | 입점, YES24 평점·리뷰 수 |
| Goodreads `book/auto_complete` | 사용 중 | 영미권 평점·평가 수 |
| 알라딘 OpenAPI | **2026-10-30 종료. 쓰지 말 것** | – |
| Amazon PA-API 5 | **2026-05 종료**, 후속 Creators API는 제휴 실적 필요 | 리뷰 분석은 UCSD Amazon Reviews 2023 데이터셋 고려 |
| 국립중앙도서관 ISBN 서지 API | 미사용(키 없음) | 원서명 필드 없음. 출간 예정 번역서 확인용 보조 |
| 카카오 책 검색 | 미사용(키 없음) | `translators` 필드 보조 |

YES24 이용 정책: 화면에 YES24 출처 표기 + 상품 링크 연결. **전체 도서 정보를 수집해 자체 DB로 쌓거나 재배포 금지**(조회한 책 단위 캐시는 허용). 키 공유 금지.

## 번역본 매칭 규칙 (scripts/eval_sheet.py `find_korean`)
입력은 원제 + 한글 저자명만. 시트의 한국어 제목은 쓰지 않는다.
1. YES24 BOOK 검색: 저자 전체명(3페이지) → 성만(2페이지) → 성+원제 → 원제. pageSize=100이어도 **결과는 최대 40건**이다.
2. 저자 일치는 성의 음역 자음 골격 비교(`author_ok`, ratio ≥ 0.7): 헤론↔헤런, 카레이루↔캐리루, 헤이즈↔헤이스 허용.
3. `originalTitle` 대조: 정규화(관사·Series·Trilogy 제거, 숫자 단어→숫자) 후 일치/포함(10자 이상만)/유사도 ≥ 0.75 → "원제 일치".
4. 원제 필드가 비면 한국어 제목을 로마자 골격으로 바꿔 원제와 비교(≥ 0.7) → "음역 일치 ⚠️". 제목에 저자 이름이 든 책은 제외.
5. 번역 여부는 `author` 문자열의 "역"으로 판단한다. `originalTranslation` 필드는 값이 엉망이라 쓰지 않는다.
6. 큰글자·세트·청소년·어린이판은 본판 선정에서 뺀다.

알려진 함정: YES24 검색어 자동 교정(엉뚱한 저자 결과가 섞임) → 저자 필터 필수 · EBOOK 카테고리 검색은 일부 전자책을 놓침 → 종이책 detail=Y의 `eBookLink`로 보정 · 조회 실패를 '미입점'으로 쓰지 말고 '확인 불가'로.

## 구조 (2026-11-13 병합)
추천 엔진(앞단)이 목록을 만들고 웹앱(뒷단)이 보여 준다. 두 목록 종류가 같은 책 형식(`stores`, `korean`, `goodreads`, `cover`, `review`, `screen`)을 쓴다.
- `scripts/matching.py` — 원제+저자 → YES24 국내판(`find_korean`). build_data · build_query · eval_sheet 공용.
- `scripts/build_data.py` — 조회 함수 모음 + `enrich(book)`(책 한 권에 전부 붙이기) + 기준 시트 목록 생성. 호스트별 간격을 지키며 6권씩 동시에 조회한다.
- `scripts/build_query.py` — 추천 목록 → 단계별 저장(목록 먼저 → 책마다 갱신) → xlsx(보조).
- `scripts/build_site.py` — `data/books.json` + `data/queries/*.result.json` → `data/lists.js`(웹앱이 읽는 파일).
- `scripts/collect_reviews.py`, `summarize_reviews.py` — 독자 리뷰 수집(Goodreads·리디·YES24) → 요약 `data/summaries.json`.
- `scripts/collect_adaptations.py` — 영상화 작품·국내 OTT(위키데이터 + TMDB) → `data/adaptations.json`.
- 웹앱: `index.html`, `app.js`, `app.css`. 배포 https://gnuesnuh.github.io/spy-bookshelf/ (공개 저장소 gnuesnuh/spy-bookshelf, main 푸시 → Pages).

## 명령
```
python scripts/build_data.py [--refresh]            # 기준 시트 → data/books.json + data/lists.js
python scripts/build_query.py <slug> [--list]       # data/queries/<slug>.json → <slug>.result.json + lists.js + 추천_<질의>.xlsx
                                                    #   --list: 목록만 먼저 올림(입점 칸은 웹앱에서 '조회 중')
python scripts/collect_adaptations.py [slug]        # 영상화·OTT. 끝난 뒤 build_data/build_query 를 다시 돌려 반영
python scripts/collect_reviews.py [slug]            # 리뷰 수집 → data/reviews/<id>.json (Goodreads 는 느림: 권당 수 초)
python scripts/summarize_reviews.py                 # 수집 리뷰 → 요약. 구독으로 돌릴 때는 세션이 직접 요약해 merge_summaries.py 로 합친다
python scripts/eval_sheet.py [lo hi]                # 번역본 매칭 채점
python scripts/make_gold.py                         # 채점 결과 + 수동 판정 → data/gold.json
python scripts/yes24_lookup.py "검색어" ...          # YES24 수동 조회
```
- 요청은 `data/cache/`에 URL 해시로 캐시. 빈 응답은 캐시하지 않음. 호스트별 최소 간격: 기본 0.6초, YES24 API 0.25초, Goodreads 1.5초.
- 새 추천 질의 순서: 목록 작성 → `build_query <slug> --list` 후 푸시(목록 먼저 공개) → `build_query <slug>` 후 푸시 → 리뷰·영상화 수집 → 요약 → `build_query <slug>` 후 푸시.
- 캐시가 없을 때 24권 국내 정보 부착은 1분 안팎(이전 순차 방식은 약 7분).
- 이 폴더에서는 파일 삭제가 막혀 있을 수 있다(원격 세션). 캐시는 덮어쓰기로 갱신.

## 알아 둘 것
- YES24 종이책의 `eBookLink`가 있어도 그 전자책이 절판일 수 있다(수영의 이유, 레드 스패로우). `matching.item_detail`로 판매 여부를 확인하고, 조회되지 않으면 '연결된 eBook은 절판·판매 종료'로 둔다.
- YES24 API는 검색 결과가 없으면 404 + `SEARCH_001`을 준다 → 실패가 아니라 '없음'으로 처리(fetch가 처리함).
- 위키데이터 질의 서비스는 장애 시 분당 1회로 제한한다(429). 그때는 영상화 상태가 '확인 불가'로 남으니 나중에 다시 돌린다.
- TMDB 제목 검색만으로는 동명 작품이 섞인다(개의 힘 ↔ 〈파워 오브 도그〉). 제작진에 원작자 이름이 있을 때만 인정한다.
- 리뷰 원문(`data/reviews/`), 캐시, `.env`, xlsx는 공개 저장소에 올리지 않는다(.gitignore).
- 모델 호출은 구독으로 한다(`docs/PLAN.md` 12절). `ANTHROPIC_API_KEY`를 설정하면 API로 과금된다.

## 작업 원칙
- 국내판 판정은 정확도 우선: 확정 ✅ / 유력 ⚠️ / 불명 ❓ 3단계로 표시하고, 근거 없는 '가능' 표기 금지.
- 수상 이력·추천 근거는 실제 출처를 확인한 것만 쓴다.
- 비밀키(.env)는 출력·커밋하지 않는다(.gitignore에 포함).
