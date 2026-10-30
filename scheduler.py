"""Heuristic Round Robin task scheduling on a real local Kubernetes cluster."""
import argparse
import concurrent.futures
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path
import time

import kube_backend as kube

BASE = Path(__file__).resolve().parent


def mapping(count, worker_count):
    if count < 1 or worker_count < 1:
        raise ValueError("Task and worker counts must be positive")
    return [i % worker_count for i in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["plan", "verify", "run"])
    parser.add_argument("--dataset", help="Optional custom dataset path")
    parser.add_argument("--dataset-size", type=int, choices=range(100, 1001, 50), default=100)
    parser.add_argument("--tasks", type=int, help="Optional subset; default executes the entire selected dataset")
    parser.add_argument("--iterations-per-mi", type=float, default=10)
    parser.add_argument("--output", default=str(BASE / "runs" / time.strftime("%Y%m%d-%H%M%S")))
    args = parser.parse_args()
    data = kube.inventory()
    if args.mode == "verify":
        evidence = kube.verify(data)
        print(json.dumps(evidence, indent=2))
        kube.print_topology(evidence)
        return
    dataset = Path(args.dataset) if args.dataset else BASE / "data" / f"GoCJ_Dataset_{args.dataset_size}.txt"
    lengths = [int(line.strip()) for line in dataset.read_text().splitlines() if line.strip()]
    if not args.dataset and len(lengths) != args.dataset_size:
        raise ValueError("Dataset length does not match its declared size")
    task_count = len(lengths) if args.tasks is None else args.tasks
    if not 1 <= task_count <= len(lengths) or any(n <= 0 for n in lengths):
        raise ValueError("Invalid task count or nonpositive GoCJ length")
    if not math.isfinite(args.iterations_per_mi) or args.iterations_per_mi <= 0:
        raise ValueError("iterations-per-mi must be positive and finite")
    assignments = mapping(task_count, len(data["workers"]))
    jobs = [{"task": i, "mi": lengths[i], "worker_index": assignments[i],
             "iterations": max(1, int(lengths[i] * args.iterations_per_mi))} for i in range(task_count)]
    dataset_info = {"dataset": dataset.name, "dataset_tasks": len(lengths),
                    "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest()}
    if args.mode == "plan":
        print(json.dumps({"mode": "plan-only", **dataset_info, "inventory": data, "jobs": jobs}, indent=2))
        return
    evidence = kube.verify(data)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    (out / "topology.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    (out / "plan.json").write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    source = (BASE / "worker.py").read_text(encoding="utf-8")
    epoch = time.perf_counter()

    def queue(index):
        worker = data["workers"][index]
        rows = []
        for job in (j for j in jobs if j["worker_index"] == index):
            row = {**job, "worker": worker["id"], "host": worker["host"],
                   "pod": worker["pod"], "node": worker["node"], "pod_uid": worker["uid"],
                   "start_s": time.perf_counter() - epoch}
            try:
                result = json.loads(kube.execute(worker, job, source))
                if result["task"] != job["task"] or result["iterations"] != job["iterations"]:
                    raise ValueError("Worker result identity mismatch")
                row.update(result, status="ok", error="")
            except Exception as exc:
                row.update(status="failed", error=str(exc), wall_s=0, cpu_s=0, digest="")
            row["finish_s"] = time.perf_counter() - epoch
            rows.append(row)
        return rows

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(data["workers"])) as pool:
        rows = [row for batch in pool.map(queue, range(len(data["workers"]))) for row in batch]
    elapsed = time.perf_counter() - epoch
    rows.sort(key=lambda r: r["task"])
    with (out / "tasks.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    failed = sum(r["status"] != "ok" for r in rows)
    summary = {"algorithm": "RR", "mode": "real-kubernetes-exec", **dataset_info, "tasks": len(rows),
               "failed": failed, "makespan_s": elapsed,
               "average_wait_s": sum(r["start_s"] for r in rows) / len(rows),
               "task_cpu_utilization_pct": 100 * sum(r["cpu_s"] for r in rows) / (elapsed * len(data["workers"])),
               "iterations_per_mi": args.iterations_per_mi}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    report = kube.format_report(summary, evidence, rows, out)
    (out / "report.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(str(exc)) from exc
