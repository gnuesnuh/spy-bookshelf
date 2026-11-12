"""단계 2 소스 수집 계획. axes.json(고른 축) + source_recipes.json → data/queries/<slug>.plan.json 과 화면 출력.
사용법: python scripts/plan_sources.py <slug> [--genre nonfiction]
고른 축(chosen)의 search_terms 로 검색어를 만든다. 축을 여러 개 고르면 모두 합친다."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
slug = sys.argv[1]
genre = sys.argv[sys.argv.index("--genre") + 1] if "--genre" in sys.argv else "nonfiction"
ax = json.loads((ROOT / "data/queries" / (slug + ".axes.json")).read_text(encoding="utf-8"))
rec = json.loads((ROOT / "scripts/source_recipes.json").read_text(encoding="utf-8"))
chosen = ax.get("chosen") or [ax["default"]["axis"]]
axes = [a for a in ax["axes"] if a["axis"] in chosen]
seed = ax["seed"]
terms = [t for a in axes for t in a["search_terms"]]
v = dict(slug=slug, orig=seed["original"], author=seed["author_orig"], genre=genre,
         axis_label=" / ".join(a["label"] for a in axes), terms_comma=", ".join(terms), terms_quoted=" ".join('"%s"' % t for t in terms))
plan = []
for r in rec["common"]:
    plan.append({"kind": r["kind"], "name": r["name"], "search": r["q"].format(**v)})
for t in terms:
    for r in rec["per_term"]:
        plan.append({"kind": r["kind"], "name": "%s (%s)" % (r["name"], t), "search": r["q"].format(term=t, **v)})
for r in rec["scripts"]:
    p = {"kind": r["kind"], "name": r["name"], "cmd": r["cmd"].format(**v)}
    if r.get("fallback"):
        p["fallback"] = r["fallback"].format(**v)
    plan.append(p)
out = {"slug": slug, "chosen": chosen, "terms": terms, "plan": plan}
(ROOT / "data/queries" / (slug + ".plan.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("고른 축:", ", ".join("%s(%s)" % (a["axis"], a["label"]) for a in axes))
for i, p in enumerate(plan, 1):
    print("%2d. [%s] %s\n    %s" % (i, p["kind"], p["name"], p.get("search") or p["cmd"]))
