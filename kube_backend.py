"""Local kind cluster: two worker nodes, two CPU worker pods per node."""
import argparse
import json
import os
from pathlib import Path
import subprocess

CLUSTER = "soka-local"
CONTEXT = "kind-" + CLUSTER
NAMESPACE = "soka-heuristik"
LABEL = "soka.lab/host"


def command(args, source=None, timeout=120):
    if args[0] in ("kind", "kubectl"):
        local_kind = Path(__file__).resolve().parent / ".tools" / "kubernetes-bin" / (
            args[0] + (".exe" if os.name == "nt" else ""))
        if local_kind.exists():
            args = [str(local_kind), *args[1:]]
    try:
        result = subprocess.run(args, input=source, text=True, capture_output=True,
                                timeout=timeout, check=True)
        return result.stdout.strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"{args[0]} belum tersedia di PATH terminal ini") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"{' '.join(args)}\n{exc.stderr or exc.stdout}") from exc


def kubectl(*args, source=None, timeout=120):
    # Never mutate or execute against the user's unrelated current context.
    return command(["kubectl", "--context", CONTEXT, "--namespace", NAMESPACE, *args],
                   source, timeout)


def inventory():
    return {"datacenter": CLUSTER, "backend": "kubernetes", "context": CONTEXT,
            "namespace": NAMESPACE, "hosts": [{"name": "host1"}, {"name": "host2"}],
            "workers": [{"id": 100 + i, "host": f"host{1 + i // 2}",
                     "pod": f"rr-worker-{i}"} for i in range(4)]}


def resources():
    items = [{"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": NAMESPACE}}]
    for vm in inventory()["workers"]:
        items.append({"apiVersion": "v1", "kind": "Pod",
                      "metadata": {"name": vm["pod"], "namespace": NAMESPACE,
                                   "labels": {"app": "rr-worker"}},
                      "spec": {"nodeSelector": {LABEL: vm["host"]},
                               "automountServiceAccountToken": False,
                               "securityContext": {"runAsNonRoot": True, "runAsUser": 10001,
                                                   "runAsGroup": 10001},
                               "containers": [{"name": "worker", "image": "python:3.12-slim",
                                               "command": ["python3", "-c", "import time; time.sleep(10**9)"],
                                               "resources": {"requests": {"cpu": "100m", "memory": "32Mi"},
                                                             "limits": {"cpu": "1", "memory": "128Mi"}},
                                               "securityContext": {"allowPrivilegeEscalation": False,
                                                                   "readOnlyRootFilesystem": True,
                                                                   "capabilities": {"drop": ["ALL"]}}}]}})
    return {"apiVersion": "v1", "kind": "List", "items": items}


def ready(obj):
    return any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in obj.get("status", {}).get("conditions", []))


def verify(data):
    nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
    pods = json.loads(kubectl("get", "pods", "-o", "json"))["items"]
    expected = {v["pod"] for v in data["workers"]}
    if {p["metadata"]["name"] for p in pods
            if p["metadata"].get("labels", {}).get("app") == "rr-worker"} != expected:
        raise ValueError("Expected exactly four labelled RR worker pods")
    hosts = {}
    for host in data["hosts"]:
        matches = [n for n in nodes if n["metadata"].get("labels", {}).get(LABEL) == host["name"]]
        if len(matches) != 1 or not ready(matches[0]):
            raise ValueError(f"Need one Ready node labelled {LABEL}={host['name']}")
        node = matches[0]
        if "node-role.kubernetes.io/control-plane" in node["metadata"].get("labels", {}):
            raise ValueError("Worker pods must not use the control-plane node")
        hosts[host["name"]] = node["metadata"]["name"]
    if len(set(hosts.values())) != 2:
        raise ValueError("Need two distinct Kubernetes worker nodes")
    evidence = {"datacenter": CLUSTER, "context": CONTEXT, "namespace": NAMESPACE,
                "mode": "local-kubernetes-container-lab", "physical_hosts_verified": False,
                "note": "Nodes are kind containers; pods are not VMs.",
                "hosts": [{"name": h, "node": n} for h, n in hosts.items()], "pods": []}
    seen = set()
    for vm in data["workers"]:
        matches = [p for p in pods if p["metadata"]["name"] == vm["pod"]]
        if len(matches) != 1:
            raise ValueError(f"Missing worker pod {vm['pod']}")
        pod = matches[0]
        if pod["status"].get("phase") != "Running" or not ready(pod) or pod["metadata"].get("deletionTimestamp"):
            raise ValueError(f"Pod {vm['pod']} is not Running/Ready")
        if pod["spec"].get("nodeName") != hosts[vm["host"]]:
            raise ValueError(f"Pod {vm['pod']} is placed on the wrong worker node")
        uid = pod["metadata"]["uid"]
        if not uid or uid in seen:
            raise ValueError("Pod UIDs must be unique")
        seen.add(uid)
        containers = pod["spec"]["containers"]
        if len(containers) != 1 or containers[0]["name"] != "worker" or str(
                containers[0].get("resources", {}).get("limits", {}).get("cpu")) not in ("1", "1000m"):
            raise ValueError("Workers require exactly one container with a 1 CPU limit")
        kubectl("exec", vm["pod"], "-c", "worker", "--", "python3", "--version")
        # This run uses the exact UID checked here, even if a same-name pod is replaced later.
        vm["uid"] = uid
        vm["node"] = hosts[vm["host"]]
        evidence["pods"].append({"pod": vm["pod"], "host": vm["host"], "node": hosts[vm["host"]],
                                 "uid": uid, "phase": pod["status"]["phase"], "cpu_limit": 1})
    return evidence


def execute(vm, job, source):
    current = kubectl("get", "pod", vm["pod"], "-o", "json")
    if json.loads(current)["metadata"]["uid"] != vm["uid"]:
        raise ValueError("Worker pod was replaced during the experiment")
    return kubectl("exec", "-i", vm["pod"], "-c", "worker", "--", "python3", "-",
                   str(job["task"]), str(job["iterations"]), source=source, timeout=3600)


def print_topology(evidence):
    print("\nTOPOLOGI EKSEKUSI KUBERNETES LOKAL")
    print("1 cluster -> 2 worker node -> masing-masing 2 pod worker (4 pod)")
    print("Control-plane: 1 node tambahan untuk pengelolaan cluster")
    for host in evidence["hosts"]:
        names = [p["pod"] for p in evidence["pods"] if p["host"] == host["name"]]
        print(f"  {host['node']} -> {', '.join(names)}")
    print("Lab satu laptop: node berupa container kind, pod bukan VM.")


def format_report(summary, evidence, rows, output):
    width = 82
    line = "=" * width
    def metric(label, value):
        return f"  {label:<28}: {value}"

    successful = summary["tasks"] - summary["failed"]
    lines = [line, "HASIL EKSEKUSI REAL WORLD - KUBERNETES LOKAL".center(width), line,
             metric("Algoritma", "Round Robin (RR) - heuristik"),
             metric("Cluster", evidence["datacenter"]),
             metric("Dataset", summary.get("dataset", "GoCJ")),
             metric("Status", "BERHASIL" if not summary["failed"] else "ADA TASK GAGAL"), "",
             "RINGKASAN TASK", "-" * width,
             metric("Total task", summary["tasks"]),
             metric("Selesai / gagal", f"{successful} / {summary['failed']}"),
             metric("Makespan", f"{summary['makespan_s']:.3f} detik"),
             metric("Rata-rata waktu tunggu", f"{summary['average_wait_s']:.3f} detik"),
             metric("Utilisasi CPU task", f"{summary['task_cpu_utilization_pct']:.2f} %"),
             metric("Skala iterasi per MI", f"{summary['iterations_per_mi']:g}"), "",
             "PEMBAGIAN TASK PADA WORKER", "-" * width,
             f"  {'NODE':<26} {'POD':<16} {'TASK':>7} {'SELESAI':>9} {'GAGAL':>7}",
             "-" * width]
    for pod in evidence["pods"]:
        assigned = [r for r in rows if r.get("pod") == pod["pod"]]
        done = sum(r["status"] == "ok" for r in assigned)
        lines.append(f"  {pod['node']:<26} {pod['pod']:<16} {len(assigned):>7} {done:>9} {len(assigned) - done:>7}")
    lines += ["", "TOPOLOGI", "-" * width,
              "  1 cluster -> 2 worker node -> 2 pod per worker (total 4 pod)",
              "  1 control-plane tambahan untuk pengelolaan cluster.",
              "  Node kind berupa container; pod bukan VM.", "",
              "FILE HASIL", "-" * width]
    path = str(Path(output).resolve())
    # WSL drive paths are also shown as native Windows paths for easy navigation.
    parts = Path(output).resolve().parts
    if len(parts) > 3 and parts[1] == "mnt" and len(parts[2]) == 1:
        path = parts[2].upper() + ":\\" + "\\".join(parts[3:])
    lines += [f"  Folder : {path}",
              "  File   : report.txt, summary.json, tasks.csv, topology.json, plan.json", "",
              "  Makespan termasuk overhead kubectl; CPU task bukan utilisasi laptop.", line]
    return "\n".join(lines)


def setup():
    command(["docker", "info"], timeout=30)
    clusters = command(["kind", "get", "clusters"]).splitlines()
    if CLUSTER not in clusters:
        print("Membuat cluster kind; download image pertama dapat memerlukan beberapa menit.", flush=True)
        command(["kind", "create", "cluster", "--name", CLUSTER, "--config",
                 str(Path(__file__).parent / "kubernetes" / "kind.yaml"), "--wait", "180s"], timeout=900)
    # Check this is our two-node worker layout before applying resources.
    nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
    for host in ("host1", "host2"):
        if sum(n["metadata"].get("labels", {}).get(LABEL) == host for n in nodes) != 1:
            raise ValueError("Existing cluster has a different layout; no resources applied")
    print("Menyiapkan empat pod worker; menunggu image Python dan status Ready.", flush=True)
    kubectl("apply", "-f", "-", source=json.dumps(resources()))
    kubectl("wait", "--for=condition=Ready", "pods", "-l", "app=rr-worker", "--timeout=300s", timeout=330)
    print_topology(verify(inventory()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "verify"])
    args = parser.parse_args()
    try:
        if args.action == "setup":
            setup()
        else:
            print_topology(verify(inventory()))
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, str(exc) + "\n")
