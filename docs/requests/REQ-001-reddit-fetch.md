# REQ-001 — Reddit 추천 스레드 수집 (로컬 실행 필요)

- 요청일: 2026-11-13
- 요청자: 클라우드 세션의 Claude (사용자 대신 작성)
- 실행 주체: **사용자 PC에서 도는 Claude Code** (로컬 터미널)
- 상태: 대기

## 왜 로컬에서 해야 하나
Reddit은 클라우드·데이터센터 IP의 요청을 403으로 막는다. 클라우드 세션과 그 세션이 연결한 셸은 중계 서버를 거쳐 나가서 막힌다.
사용자 PC의 Python에서 공개 `.json` 엔드포인트를 부르면 된다. 웹 읽기 도구(WebFetch)가 아니라 아래 스크립트를 쓴다.

## 할 일
1. `.env`에 `REDDIT_USER_AGENT`가 본인 아이디로 들어 있는지 확인(값은 출력하지 말 것).
2. Books 폴더에서 아래 두 명령을 차례로 실행한다. 각각 5~10분(요청 사이 7초 대기).
   ```
   python scripts/reddit_fetch.py barbarians "books like barbarians at the gate" "best business books wall street" "best books about private equity" "best finance narrative nonfiction"
   python scripts/reddit_fetch.py tinker "books like tinker tailor soldier spy" "best spy novels" "spy thriller recommendations"
   ```
3. 결과 확인: `data/reddit/barbarians.json`, `data/reddit/tinker.json`이 생기고 스레드 수·댓글 수가 출력된다.
   - HTTP 429가 나오면 스크립트가 1분 기다렸다 재시도한다. 403이 계속되면 중단하고 그대로 기록한다.
4. 이 파일의 '결과' 절에 날짜, 스레드 수, 댓글 수, 오류를 적고 상태를 '완료'로 바꾼다.

## 지키는 것
- 개인·비상업 용도, 소량(분당 10회 이하). 결과 JSON을 외부에 재배포하지 않는다.
- 리뷰·댓글 원문을 결과물(xlsx)에 그대로 싣지 않는다. 책 이름 집계와 요약에만 쓴다.

## 결과
(실행 후 기록)
