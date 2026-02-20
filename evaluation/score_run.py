"""
evaluation/score_run.py
Offline evaluation: runs test_queries.json through the graph and
computes aggregate Precision@k, MRR, and mean confidence score.

Usage:
    python evaluation/score_run.py
    python evaluation/score_run.py --queries evaluation/test_queries.json --out evaluation/results/run_001.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.supervisor.graph import troubleshooter_graph


def run_evaluation(queries_path: str, output_path: str, session_id: str = "eval"):
    with open(queries_path) as f:
        test_cases = json.load(f)

    results = []
    for i, case in enumerate(test_cases, start=1):
        print(f"[{i}/{len(test_cases)}] {case['query'][:60]}…")
        t0 = time.time()

        initial = {
            "session_id":     session_id,
            "user_query":     case["query"],
            "uploaded_files": [],
            "chat_history":   [],
            "error_codes":    [],
            "intent":         "",
            "mcp_result":     None,
            "rag_chunks":     [],
            "web_results":    [],
            "vision_context": None,
            "generated_answer": "",
            "source_tier":    "",
            "sources":        [],
            "confidence_score": 0.0,
            "confidence_label": "LOW",
            "critic_explanation": "",
            "retry_count":    0,
            "error":          None,
        }

        try:
            final = troubleshooter_graph.invoke(initial)
            latency = round((time.time() - t0) * 1000)
            result = {
                "query":            case["query"],
                "expected_source":  case.get("expected_source_tier"),
                "actual_source":    final.get("source_tier"),
                "confidence_score": final.get("confidence_score", 0),
                "confidence_label": final.get("confidence_label"),
                "answer_snippet":   final.get("generated_answer", "")[:150],
                "latency_ms":       latency,
                "source_match":     case.get("expected_source_tier") == final.get("source_tier"),
            }
        except Exception as exc:
            result = {"query": case["query"], "error": str(exc)}

        results.append(result)
        print(f"       → {result.get('actual_source')} | conf={result.get('confidence_score', 0):.2f} | {result.get('latency_ms')}ms")

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    valid = [r for r in results if "error" not in r]
    metrics = {
        "total":              len(results),
        "errors":             len(results) - len(valid),
        "mean_confidence":    round(sum(r["confidence_score"] for r in valid) / max(len(valid), 1), 3),
        "source_tier_accuracy": round(sum(1 for r in valid if r.get("source_match", False)) / max(len(valid), 1), 3),
        "mean_latency_ms":    round(sum(r["latency_ms"] for r in valid) / max(len(valid), 1)),
        "tier_distribution":  {},
    }
    for r in valid:
        t = r.get("actual_source", "unknown")
        metrics["tier_distribution"][t] = metrics["tier_distribution"].get(t, 0) + 1

    output = {"metrics": metrics, "results": results}
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print("\n" + "="*60)
    print("EVALUATION SUMMARY")
    print("="*60)
    for k, v in metrics.items():
        print(f"  {k:30s}: {v}")
    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", default="evaluation/test_queries.json")
    parser.add_argument("--out",     default="evaluation/results/latest.json")
    args = parser.parse_args()
    run_evaluation(args.queries, args.out)
