"""수집한 리뷰(data/reviews/*.json)를 책마다 한국어로 요약해 data/summaries.json 에 저장한다.

사용법:  python scripts/summarize_reviews.py          (새로 수집됐거나 리뷰가 바뀐 책만)
        python scripts/summarize_reviews.py --all    (전부 다시)

Claude API 를 쓴다. `pip install -U anthropic` 후 ANTHROPIC_API_KEY 를 설정하거나 `ant auth login` 을 해 둔다.
요약은 입력 리뷰의 해시와 함께 저장되어, 리뷰가 그대로면 다시 호출하지 않는다.
리뷰가 3개 미만인 책은 요약하지 않는다(화면에는 시트 메모가 대신 보인다).
"""
import hashlib
import json
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "summaries.json"
MODEL = "claude-opus-5-5"
MIN_REVIEWS = 3

SYSTEM = """당신은 독자 리뷰를 요약해 책 고르기를 돕는 편집자입니다.
입력은 한 권의 책에 대한 실제 독자 리뷰 묶음입니다(해외: Goodreads, 국내: 리디·YES24).
리뷰에 실제로 적힌 내용만 근거로, 한국어로 요약하세요. 리뷰에 없는 평가나 줄거리를 지어내지 마세요.
- text: 2~3문장, 180자 안팎. 독자들이 공통으로 꼽는 장점과 반복되는 불만을 함께 담습니다. 결말 스포일러는 뺍니다.
- pros / cons: 각각 짧은 구절 0~3개. 여러 리뷰에 반복된 것만.
- domestic: 국내 리뷰가 있으면 해외 평과 다른 점을 한 문장으로, 없으면 빈 문자열.
리뷰 문장을 그대로 옮기지 말고 자신의 말로 정리하세요."""

SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "pros": {"type": "array", "items": {"type": "string"}},
        "cons": {"type": "array", "items": {"type": "string"}},
        "domestic": {"type": "string"},
    },
    "required": ["text", "pros", "cons", "domestic"],
    "additionalProperties": False,
}


def prompt_for(doc):
    lines = ["책: %s (%s) / %s" % (doc["title"], doc["original"], doc["author"]), ""]
    for src, rows in doc["reviews"].items():
        for r in rows:
            lines.append("[%s | 별점 %s | 공감 %s] %s" % (src, r.get("rating"), r.get("likes"), r["text"]))
    return "\n".join(lines)


def summarize(client, doc):
    resp = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # 안전 분류기가 거절하면 다른 모델로 넘긴다
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt_for(doc)}],
    )
    if resp.stop_reason != "end_turn":
        raise RuntimeError("stop_reason=%s" % resp.stop_reason)
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    done = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    client = anthropic.Anthropic()
    for f in sorted((DATA / "reviews").glob("*.json")):
        doc = json.loads(f.read_text(encoding="utf-8"))
        counts = {k: len(v) for k, v in doc["reviews"].items()}
        if sum(counts.values()) < MIN_REVIEWS:
            continue
        digest = hashlib.md5(prompt_for(doc).encode()).hexdigest()
        if "--all" not in sys.argv and done.get(doc["id"], {}).get("hash") == digest:
            continue
        try:
            s = summarize(client, doc)
        except anthropic.RateLimitError:
            print("요청 한도 초과: 잠시 뒤 다시 실행하세요.", file=sys.stderr)
            break
        except anthropic.APIStatusError as e:
            print("  !", doc["title"], e.status_code, e.message, file=sys.stderr)
            continue
        except (anthropic.APIConnectionError, RuntimeError, ValueError) as e:
            print("  !", doc["title"], e, file=sys.stderr)
            continue
        done[doc["id"]] = dict(s, sources=counts, hash=digest, by=MODEL)
        OUT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        print(doc["title"], "→", s["text"][:50])


if __name__ == "__main__":
    main()
