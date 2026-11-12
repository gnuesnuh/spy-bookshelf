# 추천 소스 목록

이 문서는 `python scripts/sources.py` 가 등록부 `scripts/sources.json` 에서 자동으로 만든다. 직접 고치지 말고 등록부를 고친다.
소스를 추가하려면: `python scripts/sources.py --probe 언어:"문서명"` 으로 표 구조를 보고 → 등록부에 항목 추가 → `python scripts/sources.py <id>` 로 건수·표본을 확인한다.

상태: ✅ 수집됨 · ⚠️ 수집됐지만 건수가 적음(표 일부만 읽힘) · ❌ 못 읽음

## 영미권

| 상태 | 소스 | 종류 | 장르 | 연도 | 건수(수상) | 가중치 | 비고 |
|---|---|---|---|---|---|---|---|
| ✅ | [Edgar Award (Best Novel)](https://en.wikipedia.org/wiki/Edgar_Allan_Poe_Award_for_Best_Novel) `edgar` | 어워드 | mystery | 1954~2026 | 369 (73) | 1.0 |  |
| ✅ | [CWA Gold Dagger](https://en.wikipedia.org/wiki/Gold_Dagger) `gold_dagger` | 어워드 | mystery | 1955~2026 | 288 (72) | 1.0 |  |
| ✅ | [CWA Ian Fleming Steel Dagger](https://en.wikipedia.org/wiki/Ian_Fleming_Steel_Dagger) `steel_dagger` | 어워드 | mystery, spy | 2002~2024 | 137 (23) | 1.0 |  |
| ✅ | [Anthony Award (Best Novel)](https://en.wikipedia.org/wiki/Anthony_Award_for_Best_Novel) `anthony` | 어워드 | mystery | 1986~2023 | 209 (38) | 0.8 |  |
| ✅ | [Hugo Award (Best Novel)](https://en.wikipedia.org/wiki/Hugo_Award_for_Best_Novel) `hugo` | 어워드 | sf | 1953~2026 | 371 (77) | 1.0 |  |
| ✅ | [Nebula Award (Best Novel)](https://en.wikipedia.org/wiki/Nebula_Award_for_Best_Novel) `nebula` | 어워드 | sf | 1965~2025 | 389 (62) | 1.0 |  |
| ✅ | [Arthur C. Clarke Award](https://en.wikipedia.org/wiki/Arthur_C._Clarke_Award) `clarke` | 어워드 | sf | 1987~2026 | 247 (40) | 0.9 |  |
| ✅ | [Locus Award (SF Novel)](https://en.wikipedia.org/wiki/Locus_Award_for_Best_Science_Fiction_Novel) `locus_sf` | 어워드 | sf | 1980~2026 | 47 (47) | 0.8 |  |
| ✅ | [Booker Prize](https://en.wikipedia.org/wiki/Booker_Prize) `booker` | 어워드 | literary | 1969~2026 | 61 (61) | 1.0 |  |
| ⚠️ | [International Booker Prize](https://en.wikipedia.org/wiki/International_Booker_Prize) `intl_booker` | 어워드 | literary | 2016~2026 | 11 (11) | 0.9 |  |
| ✅ | [Pulitzer Prize for Fiction](https://en.wikipedia.org/wiki/Pulitzer_Prize_for_Fiction) `pulitzer_fic` | 어워드 | literary | 1918~2026 | 195 (100) | 1.0 |  |
| ✅ | [National Book Award (Fiction)](https://en.wikipedia.org/wiki/National_Book_Award_for_Fiction) `nba_fic` | 어워드 | literary | 1950~2026 | 483 (83) | 0.9 |  |
| ⚠️ | [Women's Prize for Fiction](https://en.wikipedia.org/wiki/Women%27s_Prize_for_Fiction) `womens` | 어워드 | literary | 1938~2003 | 14 (14) | 0.8 | 일부만 읽힘(문서가 표·목록 혼합) |
| ✅ | [Pulitzer Prize for General Nonfiction](https://en.wikipedia.org/wiki/Pulitzer_Prize_for_General_Nonfiction) `pulitzer_gnf` | 어워드 | nonfiction | 1962~2026 | 176 (73) | 1.0 |  |
| ✅ | [Pulitzer Prize for History](https://en.wikipedia.org/wiki/Pulitzer_Prize_for_History) `pulitzer_hist` | 어워드 | nonfiction, history | 1917~2026 | 210 (48) | 0.9 |  |
| ✅ | [National Book Award (Nonfiction)](https://en.wikipedia.org/wiki/National_Book_Award_for_Nonfiction) `nba_nf` | 어워드 | nonfiction | 1935~2025 | 839 (165) | 0.9 |  |
| ✅ | [Baillie Gifford Prize](https://en.wikipedia.org/wiki/Baillie_Gifford_Prize) `baillie` | 어워드 | nonfiction | 1999~2026 | 166 (28) | 1.0 |  |
| ✅ | [FT Business Book of the Year](https://en.wikipedia.org/wiki/Financial_Times_Business_Book_of_the_Year_Award) `ft_business` | 어워드 | nonfiction, business | 2005~2025 | 120 (120) | 1.0 |  |
| ✅ | [Royal Society Science Book Prize](https://en.wikipedia.org/wiki/Royal_Society_Science_Books_Prize) `royal_science` | 어워드 | nonfiction, science | 1988~2026 | 175 (39) | 1.0 |  |
| ✅ | [Wolfson History Prize](https://en.wikipedia.org/wiki/Wolfson_History_Prize) `wolfson` | 어워드 | nonfiction, history | 1972~2026 | 146 (9) | 0.8 |  |
| ✅ | [Kirkus Prize](https://en.wikipedia.org/wiki/Kirkus_Prize) `kirkus` | 어워드 | literary, nonfiction | 2014~2026 | 234 (39) | 0.7 |  |
| ✅ | [Publishers Weekly 연간 베스트셀러 소설 (2010s)](https://en.wikipedia.org/wiki/Publishers_Weekly_list_of_bestselling_novels_in_the_United_States_in_the_2010s) `pw_2010s` | 연간 랭킹 | bestseller | 2010~2019 | 100 (0) | 0.6 | 판매량 축. 장르 질의에서는 이미 뽑힌 작품의 가점으로만 쓴다 |
| ✅ | [Publishers Weekly 연간 베스트셀러 소설 (2020s)](https://en.wikipedia.org/wiki/Publishers_Weekly_list_of_bestselling_novels_in_the_United_States_in_the_2020s) `pw_2020s` | 연간 랭킹 | bestseller | 2020~2025 | 60 (0) | 0.6 | 판매량 축. 장르 질의에서는 이미 뽑힌 작품의 가점으로만 쓴다 |

## 일본

| 상태 | 소스 | 종류 | 장르 | 연도 | 건수(수상) | 가중치 | 비고 |
|---|---|---|---|---|---|---|---|
| ✅ | [このミステリーがすごい! (国内編)](https://ja.wikipedia.org/wiki/%E3%81%93%E3%81%AE%E3%83%9F%E3%82%B9%E3%83%86%E3%83%AA%E3%83%BC%E3%81%8C%E3%81%99%E3%81%94%E3%81%84%21) `konomys` | 연간 랭킹 | mystery | 1988~2026 | 386 (0) | 1.0 | 연도별 1~10위 |
| ✅ | [週刊文春ミステリーベスト10 (国内部門)](https://ja.wikipedia.org/wiki/%E9%80%B1%E5%88%8A%E6%96%87%E6%98%A5%E3%83%9F%E3%82%B9%E3%83%86%E3%83%AA%E3%83%BC%E3%83%99%E3%82%B9%E3%83%8810) `bunshun` | 연간 랭킹 | mystery | 1983~2025 | 437 (0) | 1.0 | 연도별 1~10위 |
| ✅ | [本格ミステリ・ベスト10](https://ja.wikipedia.org/wiki/%E6%9C%AC%E6%A0%BC%E3%83%9F%E3%82%B9%E3%83%86%E3%83%AA%E3%83%BB%E3%83%99%E3%82%B9%E3%83%8810) `honkaku_best` | 연간 랭킹 | mystery | 2000~2026 | 272 (0) | 0.9 |  |
| ✅ | [ミステリが読みたい!](https://ja.wikipedia.org/wiki/%E3%83%9F%E3%82%B9%E3%83%86%E3%83%AA%E3%81%8C%E8%AA%AD%E3%81%BF%E3%81%9F%E3%81%84%21) `mys_yomitai` | 연간 랭킹 | mystery | 2008~2026 | 190 (0) | 0.8 |  |
| ✅ | [本格ミステリ大賞](https://ja.wikipedia.org/wiki/%E6%9C%AC%E6%A0%BC%E3%83%9F%E3%82%B9%E3%83%86%E3%83%AA%E5%A4%A7%E8%B3%9E) `honkaku` | 어워드 | mystery | 2001~2026 | 130 (30) | 1.0 |  |
| ❌ | [日本推理作家協会賞](https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%AC%E6%8E%A8%E7%90%86%E4%BD%9C%E5%AE%B6%E5%8D%94%E4%BC%9A%E8%B3%9E) `suiri` | 어워드 | mystery | - | 0 | 1.0 | 보류: 수상작이 부문별 목록 형식이라 현재 파서로 못 읽는다 |
| ✅ | [江戸川乱歩賞](https://ja.wikipedia.org/wiki/%E6%B1%9F%E6%88%B8%E5%B7%9D%E4%B9%B1%E6%AD%A9%E8%B3%9E) `ranpo` | 어워드 | mystery | 1955~2026 | 335 (81) | 0.8 | 신인 공모상 — 데뷔작 |
| ✅ | [大藪春彦賞](https://ja.wikipedia.org/wiki/%E5%A4%A7%E8%97%AA%E6%98%A5%E5%BD%A6%E8%B3%9E) `oyabu` | 어워드 | mystery | 1999~2026 | 132 (132) | 0.7 |  |
| ✅ | [本屋大賞](https://ja.wikipedia.org/wiki/%E6%9C%AC%E5%B1%8B%E5%A4%A7%E8%B3%9E) `honya` | 연간 랭킹 | literary, bestseller | 2012~2026 | 150 (0) | 1.0 | 서점 직원 투표. 2012년 이후 1~10위 |
| ✅ | [直木三十五賞](https://ja.wikipedia.org/wiki/%E7%9B%B4%E6%9C%A8%E4%B8%89%E5%8D%81%E4%BA%94%E8%B3%9E) `naoki` | 어워드 | literary | 1935~2026 | 234 (234) | 1.0 |  |
| ✅ | [芥川龍之介賞](https://ja.wikipedia.org/wiki/%E8%8A%A5%E5%B7%9D%E9%BE%8D%E4%B9%8B%E4%BB%8B%E8%B3%9E) `akutagawa` | 어워드 | literary | 1935~2026 | 221 (221) | 0.9 |  |
| ✅ | [山本周五郎賞](https://ja.wikipedia.org/wiki/%E5%B1%B1%E6%9C%AC%E5%91%A8%E4%BA%94%E9%83%8E%E8%B3%9E) `yamamoto` | 어워드 | literary | 1988~2026 | 191 (191) | 0.8 |  |
| ✅ | [吉川英治文学新人賞](https://ja.wikipedia.org/wiki/%E5%90%89%E5%B7%9D%E8%8B%B1%E6%B2%BB%E6%96%87%E5%AD%A6%E6%96%B0%E4%BA%BA%E8%B3%9E) `yoshikawa_new` | 어워드 | literary | 1980~2026 | 251 (251) | 0.7 |  |
| ✅ | [日本SF大賞](https://ja.wikipedia.org/wiki/%E6%97%A5%E6%9C%ACSF%E5%A4%A7%E8%B3%9E) `nihon_sf` | 어워드 | sf | 1980~2025 | 48 (48) | 1.0 |  |
| ✅ | [星雲賞](https://ja.wikipedia.org/wiki/%E6%98%9F%E9%9B%B2%E8%B3%9E) `seiun` | 어워드 | sf | 1970~2026 | 58 (58) | 0.9 | 日本長編部門만 |
| ✅ | [大宅壮一ノンフィクション賞](https://ja.wikipedia.org/wiki/%E5%A4%A7%E5%AE%85%E5%A3%AE%E4%B8%80%E3%83%8E%E3%83%B3%E3%83%95%E3%82%A3%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E8%B3%9E) `oya` | 어워드 | nonfiction | 1970~2026 | 92 (92) | 1.0 |  |
| ✅ | [講談社本田靖春ノンフィクション賞](https://ja.wikipedia.org/wiki/%E8%AC%9B%E8%AB%87%E7%A4%BE%E6%9C%AC%E7%94%B0%E9%9D%96%E6%98%A5%E3%83%8E%E3%83%B3%E3%83%95%E3%82%A3%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E8%B3%9E) `kodansha_nf` | 어워드 | nonfiction | 1968~2026 | 78 (78) | 0.9 |  |
| ✅ | [開高健ノンフィクション賞](https://ja.wikipedia.org/wiki/%E9%96%8B%E9%AB%98%E5%81%A5%E3%83%8E%E3%83%B3%E3%83%95%E3%82%A3%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E8%B3%9E) `kaiko` | 어워드 | nonfiction | 2003~2026 | 24 (22) | 0.8 |  |
| ✅ | [新書大賞](https://ja.wikipedia.org/wiki/%E6%96%B0%E6%9B%B8%E5%A4%A7%E8%B3%9E) `shinsho` | 연간 랭킹 | nonfiction | 2008~2026 | 137 (0) | 0.9 | 연도별 1~10위 |
| ✅ | [小林秀雄賞](https://ja.wikipedia.org/wiki/%E5%B0%8F%E6%9E%97%E7%A7%80%E9%9B%84%E8%B3%9E) `kobayashi` | 어워드 | nonfiction | 2002~2026 | 25 (25) | 0.7 |  |
| ❌ | [本屋大賞 ノンフィクション本大賞](https://ja.wikipedia.org/wiki/Yahoo%21%E3%83%8B%E3%83%A5%E3%83%BC%E3%82%B9_%E6%9C%AC%E5%B1%8B%E5%A4%A7%E8%B3%9E_%E3%83%8E%E3%83%B3%E3%83%95%E3%82%A3%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E6%9C%AC%E5%A4%A7%E8%B3%9E) `honya_nf` | 어워드 | nonfiction | - | 0 | 0.9 | 위키백과 요청 제한으로 미수집 — 다시 실행하면 받는다 |

## 아직 못 넣은 소스

- 독자 커뮤니티: Reddit(403, 공식 API 필요), 読書メーター·ブクログ(자동 접근 거부). Hacker News·Discourse 는 `scripts/community_fetch.py`.
- 언론 연간 결산(NYT 10 Best, Guardian, 朝日·読売 書評 '今年の3冊' 등): 위키백과에 표가 없어 페이지별 수집기가 필요하다.
- Goodreads Choice Awards: 위키백과에 후보 목록이 없다.
