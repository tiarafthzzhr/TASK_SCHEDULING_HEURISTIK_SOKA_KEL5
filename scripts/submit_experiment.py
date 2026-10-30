"""Create one fresh in-cluster Job, or run all original dataset sizes sequentially."""
import argparse
import json
from pathlib import Path
import secrets
import time

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kube_backend as kube


def job(size, tasks=None):
    # JSON is also a valid Kubernetes YAML manifest.
    return {"apiVersion": "batch/v1", "kind": "Job", "metadata": {
        "name": f"rr-{size}-{time.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(2)}", "namespace": kube.NAMESPACE},
        "spec": {"backoffLimit": 0, "template": {"metadata": {"labels": {"app": "rr-controller"}}, "spec": {
            "restartPolicy": "Never", "serviceAccountName": "rr-controller",
            "nodeSelector": {kube.LABEL: "host1"},
            "securityContext": {"runAsNonRoot": True, "runAsUser": 10001, "runAsGroup": 10001, "fsGroup": 10001},
            "containers": [{"name": "scheduler", "image": "soka-task-scheduler:v1", "imagePullPolicy": "Never",
                            "command": ["python3", "scheduler.py"],
                            "args": ["run", "--dataset-size", str(size)] + (["--tasks", str(tasks)] if tasks else []),
                            "env": [{"name": "SOKA_CLUSTER_MODE", "value": "k3s"},
                                    {"name": "SOKA_IN_CLUSTER", "value": "1"},
                                    {"name": "SOKA_OUTPUT_ROOT", "value": "/results"}],
                            "resources": {"requests": {"cpu": "100m", "memory": "64Mi"},
                                          "limits": {"cpu": "500m", "memory": "256Mi"}},
                            "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True,
                                                "capabilities": {"drop": ["ALL"]}},
                            "volumeMounts": [{"name": "results", "mountPath": "/results"}]}],
            "volumes": [{"name": "results", "persistentVolumeClaim": {"claimName": "rr-results"}}]}}}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-size", type=int, choices=range(100, 1001, 50), default=100)
    parser.add_argument("--all-datasets", action="store_true")
    parser.add_argument("--tasks", type=int)
    args = parser.parse_args()
    if args.tasks is not None and (args.all_datasets or not 1 <= args.tasks <= args.dataset_size):
        parser.error("Tasks must be within the selected dataset; do not combine with all-datasets")
    if kube.MODE != "k3s":
        parser.error("Set SOKA_CLUSTER_MODE=k3s and KUBECONFIG before submitting")
    kube.verify(kube.inventory())
    # Refuse concurrent controllers because they share the same four CPU workers.
    for existing in json.loads(kube.kubectl("get", "jobs", "-o", "json"))["items"]:
        if existing.get("status", {}).get("active", 0):
            parser.error("Another Job is active; wait before starting an experiment")
    for size in range(100, 1001, 50) if args.all_datasets else [args.dataset_size]:
        spec = job(size, args.tasks)
        name = spec["metadata"]["name"]
        kube.kubectl("create", "-f", "-", source=json.dumps(spec))
        print(f"Started Job {name}", flush=True)
        # Poll both failure and completion instead of waiting forever on Complete after a failure.
        deadline = time.monotonic() + 7200
        while True:
            state = json.loads(kube.kubectl("get", "job", name, "-o", "json"))
            if any(c["type"] == "Failed" and c["status"] == "True" for c in state.get("status", {}).get("conditions", [])):
                raise SystemExit(f"Job {name} failed; inspect kubectl logs job/{name}. Batch stopped.")
            if any(c["type"] == "Complete" and c["status"] == "True" for c in state.get("status", {}).get("conditions", [])):
                print(kube.kubectl("logs", f"job/{name}"), flush=True)
                break
            if time.monotonic() > deadline:
                raise SystemExit(f"Stopped waiting for {name} after 2h; Job may still run. Do not submit another run.")
            time.sleep(3)


if __name__ == "__main__":
    main()
