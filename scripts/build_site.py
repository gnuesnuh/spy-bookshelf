"""웹앱이 읽는 data/lists.js 를 만든다: 기준 시트 목록 + data/queries/*.result.json 의 추천 목록.

build_data.py, build_query.py 가 끝에 자동으로 부른다. 직접 실행해도 된다:  python scripts/build_site.py
"""
import json
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def main():
    lists = []
    paths = [DATA / "books.json"] + sorted((DATA / "queries").glob("*.result.json"))
    for p in paths:
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if not d.get("books") or "korean" not in d["books"][0]:
            continue  # 예전 형식 결과는 건너뛴다 (build_query.py 를 다시 돌리면 갱신된다)
        d.setdefault("slug", p.name.replace(".result.json", ""))
        lists.append(d)
    (DATA / "lists.js").write_text("window.BOOK_LISTS = " + json.dumps(lists, ensure_ascii=False) + ";\n",
                                   encoding="utf-8")
    print("lists.js:", ", ".join("%s(%d권)" % (d["slug"], len(d["books"])) for d in lists))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
