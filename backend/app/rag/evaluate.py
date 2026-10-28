"""Retrieval evaluation over a labelled question set.

    python -m app.rag.evaluate [--k 5]

Reports hit@1, hit@k and mean reciprocal rank (MRR) of the expected source
document, using the configured embedding model and the live index. Questions
are evaluated as an anonymous customer (public documents only).
"""
import argparse
import json
from pathlib import Path

from app.core.database import SessionLocal
from app.models.models import User, UserRole
from app.rag.embeddings import get_embedder
from app.rag.ingest import knowledge_dir
from app.rag.store import retrieve


def evaluate(db, k: int = 5) -> dict:
    cases = json.loads((knowledge_dir() / "eval" / "questions.json").read_text())
    probe = User(id="00000000-0000-0000-0000-000000000000", role=UserRole.CUSTOMER, email="eval@invalid",
                 full_name="Evaluator", hashed_password="!")
    rows, hits1, hitsk, rr = [], 0, 0, 0.0
    for case in cases:
        results = retrieve(db, case["question"], probe, k=k, min_score=0.0)
        sources = [r.source for r in results]
        rank = sources.index(case["expected_source"]) + 1 if case["expected_source"] in sources else None
        hits1 += rank == 1
        hitsk += rank is not None
        rr += 1 / rank if rank else 0
        rows.append({"question": case["question"], "expected": case["expected_source"], "rank": rank,
                     "top": sources[:3], "top_score": results[0].score if results else None})
    n = len(cases)
    return {"embedding_model": get_embedder().model_id, "k": k, "questions": n, "hit_at_1": round(hits1 / n, 3),
            f"hit_at_{k}": round(hitsk / n, 3), "mrr": round(rr / n, 3), "cases": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    with SessionLocal() as session:
        report = evaluate(session, args.k)
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    for row in report["cases"]:
        print(f"  rank={row['rank']!s:>4}  {row['question']}")
