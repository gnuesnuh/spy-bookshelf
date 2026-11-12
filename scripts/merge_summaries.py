"""data/summaries_part_*.json (id -> {text, pros, cons, domestic}) 을 data/summaries.json 에 합친다.

API 키 없이 요약을 따로 만들었을 때 쓰는 보조 스크립트. 합친 뒤 part 파일은 지운다.
해시는 summarize_reviews.py 와 같은 방식이라, 이후 API 로 돌려도 리뷰가 그대로면 다시 요약하지 않는다.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
DATA = Path(__file__).resolve().parent.parent / "data"


def prompt_for(doc):  # summarize_reviews.prompt_for 와 동일
    lines = ["책: %s (%s) / %s" % (doc["title"], doc["original"], doc["author"]), ""]
    for src, rows in doc["reviews"].items():
        for r in rows:
            lines.append("[%s | 별점 %s | 공감 %s] %s" % (src, r.get("rating"), r.get("likes"), r["text"]))
    return "\n".join(lines)


def main(by):
    out = DATA / "summaries.json"
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    for part in sorted(DATA.glob("summaries_part_*.json")):
        for bid, s in json.loads(part.read_text(encoding="utf-8")).items():
            doc = json.loads((DATA / "reviews" / (bid + ".json")).read_text(encoding="utf-8"))
            done[bid] = dict(text=s["text"], pros=s.get("pros") or [], cons=s.get("cons") or [],
                             domestic=s.get("domestic") or "",
                             sources={k: len(v) for k, v in doc["reviews"].items()},
                             hash=hashlib.md5(prompt_for(doc).encode()).hexdigest(), by=by)
        part.unlink()
    out.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(done), "summaries")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "manual")
