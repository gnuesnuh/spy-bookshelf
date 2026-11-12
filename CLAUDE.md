# Books — 도서 추천 · 국내 번역본 · 전자책 입점 확인 서비스

장르나 책 제목을 넣으면 추천 목록을 만들고, 각 책의 국내 번역본과 전자책·구독 서비스 입점 여부를 붙인다.
기획(목표·범위·작업 절차·로드맵)은 `docs/PLAN.md`, 진행 이력과 검증 수치는 `docs/PROGRESS.md`. 작업 전에 둘 다 읽을 것.
추천 요청을 받으면 `docs/PLAN.md` 6절 '사용 흐름'을 따른다.

## 열린 요청
`docs/requests/`의 상태 '대기' 요청서를 먼저 확인한다. 로컬 PC에서 실행 중이면 처리하고 결과를 요청서에 기록한다.
- REQ-001 Reddit 공개 JSON 수집 — 완료(실패: PC에서도 403). Reddit은 Gemini 경유로 대체됨
- **REQ-002 추천 목록 작성 절차 공유 — 대기.** `docs/PLAYBOOK.md`를 읽고 요청서에 답을 적는다

**추천 목록을 만들 때는 `docs/PLAYBOOK.md`를 따른다** (단계 0 도서 성격 분석 → 소스 수집 → 집계 → 단계 확장 → build_query → 검수).

## 출력 기준 (정답 형식)
기존 Google 시트(ID `10hYwTqAXoqn-qZ3u1YCN4RVWBhYQGTcBXctbljjc9mQ`, 로컬 사본 `data/sheet.xlsx`)와 같은 열 구성:
카테고리 · 한국어 제목 · 원제 · 저자 · 수상 및 선정 이력 · 영미권/국내 평점 · 리뷰 요약 및 추천 포인트 ·
YES24 eBook · 밀리의서재 · 리디셀렉트 · 크레마클럽 · 비고.
단, 시트 자체에 오류가 있다(제목 오기, 미번역 도서를 '번역됨'으로 표기, 리디셀렉트 과다 표기).
**시트 재현은 목표가 아니다.** 시트는 형식 참고용, `data/gold.json`은 번역본 매칭 회귀 테스트용으로만 쓴다.

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
| Gemini API (`GEMINI_API_KEY`, 선불) | 사용 중 | Google 검색 그라운딩으로 **Reddit 추천 후보**만 받음 (`gemini_candidates.py`). 근거 소스 1곳으로 취급, 언급 수·원문은 쓰지 않음 |
| Hacker News(Algolia)·Discourse·Lemmy | 사용 중 | 커뮤니티 추천 댓글 (`community_fetch.py`). HN은 경제경영·논픽션에 강함 |
| Reddit 직접 접근 | **불가** — Claude 도구 차단, 공개 `.json`은 PC에서도 403 | 공식 API(OAuth)는 추후 보완. 우회 수집·원문 미러링 금지 |
| ssn.so(소설넷) | **제외** — robots.txt가 ClaudeBot 등 AI 크롤러 차단 | – |

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
python scripts/sources.py [id ...] [--refresh]      # 소스 캐시: 등록부(scripts/sources.json)의 어워드·랭킹을 위키백과에서 수집
                                                    #   → data/sources/<id>.json + docs/SOURCES.md(소스 목록 문서, 자동 생성)
python scripts/sources.py --probe ja:"문서명"        # 새 소스를 등록하기 전에 표 구조 보기
python scripts/award_candidates.py <slug> --seed "흑뢰성" [--genre mystery] [--top 40]
python scripts/award_candidates.py <slug> --genre mystery [시작 끝] [--top 40] [--region en,ja]
                                                    # 질의의 '어워드 축' 후보 → data/queries/<slug>.awards.json (+ .unresolved.json)
                                                    # 목록이 아니다. 다른 근거와 합쳐 Claude Code 가 <slug>.json 을 만든다
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
- 새 추천 질의 순서 (끝까지 가야 한다 — 리뷰 요약을 빼먹으면 웹앱에 '요약 대기'가 계속 남는다):
  1. 목록 작성 → `build_query <slug> --list` 후 푸시(목록 먼저 공개)
  2. `build_query <slug>` — 국내 정보 부착 + 독자 리뷰 수집까지 한 번에 한다 → 푸시
  3. 끝에 출력되는 '요약 대기' 책들의 `data/reviews/<id>.json`을 읽고 요약 → `data/summaries_part_N.json` → `merge_summaries.py`
     (요약 형식: text 2~3문장, pros/cons 각 0~3개, domestic 한 문장 또는 "". 리뷰에 적힌 내용만 쓴다)
  4. `collect_adaptations.py <slug>` → `build_query <slug> --no-reviews` → 푸시
- 캐시가 없을 때 24권 국내 정보 부착은 1분 안팎(이전 순차 방식은 약 7분).
- 이 폴더에서는 파일 삭제가 막혀 있을 수 있다(원격 세션). 캐시는 덮어쓰기로 갱신.

## 추천 소스 (소스 캐시)
- 소스 목록의 원본은 등록부 `scripts/sources.json`, 사람이 보는 문서는 `docs/SOURCES.md`(자동 생성 — 직접 고치지 말 것).
- 소스를 추가할 때: `--probe`로 표 구조 확인 → 등록부에 항목 추가(id, name, lang, page, genres, kind, weight, parser) → `python scripts/sources.py <id>`로 건수와 표본을 눈으로 확인. 저자 칸에 부문명·출처가 들어가면 `cols`·`tables`로 조정하거나 `disabled`로 보류한다.
- parser: `table`(표의 열 이름으로 연도·제목·저자·결과를 찾음) · `list`(목록형 문서, 일본어 『제목』/영어 ''제목'') · `ja_ranked`(このミス식 순위 목록) · `honya`.
- 점수: 순위형 (11-순위) · 수상 10 · 후보 4, × 소스 가중치. 지역마다 소스 수가 달라 장르 질의는 지역 안 최고점을 100으로 맞춰 섞는다. 판매량 소스(`bestseller`)는 장르 소스에 오른 작품의 가점으로만 쓴다.
- 영어 원제 매칭은 `matching.find_korean_en`(영어 저자명으로, YES24 원제 검색). 한글 저자명은 찾은 국내판에서 가져온다.
- 위키백과는 요청이 몰리면 429를 준다(호스트 간격 4초). 실패한 소스는 다시 실행하면 받는다.

## 일본어 원제 매칭 (scripts/matching.py `find_korean_ja`)
- 입력은 일본어 제목 + 일본어 저자명. 검색 순서: 일본어 원제로 YES24 직접 검색 → 저자의 한국어 위키백과 문서명 → 저자 가나를 한글로 옮긴 이름(`kana_to_hangul`). 어느 경로든 `originalTitle`이 원제와 맞아야 인정한다.
- YES24의 일본어 원제는 구자체·기호가 섞여 있다(惡意, 黑牢城, マスカレ-ド.ライフ) → `jn()`이 신자체로 바꾸고 기호·장음을 지운다. 변환표는 matching.py의 `_KYU`.
- 원제 필드가 빈 책(여섯명의 거짓말쟁이 대학생, 흉인저의 살인 등)은 자동으로 못 잇는다. `award_candidates.py`가 `<slug>.unresolved.json`에 같은 저자의 '원제 미표기' 국내 출간작 후보를 적어 주면, **Claude Code가 후보를 보고 `scripts/ja_titles.json`에 판정을 적는다**(`"일본어 원제|일본어 저자": "국내 제목"`, 국내판 없음으로 판정하면 `""`). 판정한 제목은 저자 일치까지 확인된 뒤에만 쓰이고 '유력 ⚠️(수동 검수)'로 표시된다. 확신이 없으면 적지 않는다.
- 저자 정보(한국어 문서명·가나)는 `data/sources/ja/authors.json`에 쌓인다. 일본어 위키백과는 요청이 몰리면 429를 준다.
- 일본어 원제 책은 Goodreads를 자동 검색하지 않는다(엉뚱한 책이 잡힘). 필요하면 목록의 `grq`에 영어 제목을 적는다.
- 영상화는 Goodreads 작품 번호가 없어 아직 일본 책에 붙지 않는다.

## 알아 둘 것
- YES24 종이책의 `eBookLink`가 있어도 그 전자책이 절판일 수 있다(수영의 이유, 레드 스패로우). `matching.item_detail`로 판매 여부를 확인하고, 조회되지 않으면 '연결된 eBook은 절판·판매 종료'로 둔다.
- YES24 API는 검색 결과가 없으면 404 + `SEARCH_001`을 준다 → 실패가 아니라 '없음'으로 처리(fetch가 처리함).
- 위키데이터 질의 서비스는 장애 시 분당 1회로 제한한다(429). 그때는 영상화 상태가 '확인 불가'로 남으니 나중에 다시 돌린다.
- TMDB 제목 검색만으로는 동명 작품이 섞인다(개의 힘 ↔ 〈파워 오브 도그〉). 제작진에 원작자 이름이 있을 때만 인정한다.
- 리뷰 원문(`data/reviews/`), 캐시, `.env`, xlsx는 공개 저장소에 올리지 않는다(.gitignore).
- 모델 호출은 구독으로 한다(`docs/PLAN.md` 12절). `ANTHROPIC_API_KEY`를 설정하면 API로 과금된다.

## 작업 원칙
- **목록은 사용자가 책이나 장르를 질의했을 때만 만든다.** 소스 캐시·수집기·매칭을 고치거나 시험할 때 목록(`data/queries/<slug>.json`)을 새로 만들어 웹앱에 올리지 않는다. 시험은 기존 질의나 임시 출력으로 한다.
- 한 질의의 근거는 5곳 이상, 종류는 3가지 이상(어워드·전문가 추천·언론 결산·커뮤니티·Reddit(Gemini 경유)). 소스 캐시(`award_candidates.py`)는 그중 어워드 한 종류다.
- 국내판 판정은 정확도 우선: 확정 ✅ / 유력 ⚠️ / 불명 ❓ 3단계로 표시하고, 근거 없는 '가능' 표기 금지.
- 수상 이력·추천 근거는 실제 출처를 확인한 것만 쓴다.
- 비밀키(.env)는 출력·커밋하지 않는다(.gitignore에 포함).
