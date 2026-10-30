import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import kube_backend as kube
import scheduler
from worker import work


class KubernetesTests(unittest.TestCase):
    def test_all_original_dataset_files_match_manifest(self):
        folder = scheduler.BASE / "data"
        manifest = json.loads((folder / "manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), 22)
        for entry in manifest["files"]:
            content = (folder / entry["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
            if "tasks" in entry:
                self.assertEqual(len(content.splitlines()), entry["tasks"])

    def test_selected_dataset_runs_in_full_by_default(self):
        for size in (100, 150, 1000):
            with self.subTest(size=size), patch.object(sys, "argv", [
                    "scheduler.py", "plan", "--dataset-size", str(size)]), patch("builtins.print") as printed:
                scheduler.main()
                plan = json.loads(printed.call_args.args[0])
                self.assertEqual(len(plan["jobs"]), size)
                self.assertEqual(plan["dataset"], f"GoCJ_Dataset_{size}.txt")
                expected = [int(x) for x in (scheduler.BASE / "data" / plan["dataset"]).read_text().splitlines()]
                self.assertEqual([j["mi"] for j in plan["jobs"]], expected)

    def setUp(self):
        self.data = kube.inventory()
        condition = [{"type": "Ready", "status": "True"}]
        self.nodes = [{"metadata": {"name": "node-" + h["name"],
                                    "labels": {kube.LABEL: h["name"]}},
                       "status": {"conditions": condition}} for h in self.data["hosts"]]
        self.pods = []
        for item in kube.resources()["items"][1:]:
            pod = copy.deepcopy(item)
            pod["metadata"]["uid"] = "uid-" + pod["metadata"]["name"]
            pod["spec"]["nodeName"] = "node-" + pod["spec"]["nodeSelector"][kube.LABEL]
            pod["status"] = {"phase": "Running", "conditions": condition}
            self.pods.append(pod)

    def fake_kubectl(self, *args, source=None, timeout=120):
        if args[:2] == ("get", "nodes"):
            return json.dumps({"items": self.nodes})
        if args[:2] == ("get", "pods"):
            return json.dumps({"items": self.pods})
        if args[:2] == ("get", "pod"):
            return json.dumps(next(p for p in self.pods if p["metadata"]["name"] == args[2]))
        if "--version" in args:
            return "Python 3.12"
        if args[:2] == ("exec", "-i"):
            return json.dumps(work(int(args[-2]), int(args[-1])))
        raise AssertionError(args)

    def test_actual_placement_and_worker_identity(self):
        with patch.object(kube, "kubectl", side_effect=self.fake_kubectl):
            evidence = kube.verify(self.data)
        self.assertEqual(len(evidence["pods"]), 4)
        self.assertFalse(evidence["physical_hosts_verified"])
        self.assertEqual([v["host"] for v in self.data["workers"]], ["host1", "host1", "host2", "host2"])

    def test_reject_wrong_placement_unready_and_replaced_worker(self):
        with patch.object(kube, "kubectl", side_effect=self.fake_kubectl):
            self.pods[0]["spec"]["nodeName"] = "node-host2"
            with self.assertRaisesRegex(ValueError, "wrong worker"):
                kube.verify(self.data)
            self.pods[0]["spec"]["nodeName"] = "node-host1"
            self.pods[0]["status"]["phase"] = "Pending"
            with self.assertRaisesRegex(ValueError, "Running/Ready"):
                kube.verify(self.data)
            self.pods[0]["status"]["phase"] = "Running"
            kube.verify(self.data)
            self.pods[0]["metadata"]["uid"] = "replacement"
            with self.assertRaisesRegex(ValueError, "replaced"):
                kube.execute(self.data["workers"][0], {"task": 0, "iterations": 1}, "")

    def test_kind_commands_target_only_own_control_plane(self):
        with patch.object(kube, "command", return_value="ok") as call:
            kube.kubectl("get", "pods")
        self.assertEqual(call.call_args.args[0][:7],
                         ["docker", "exec", "soka-local-control-plane", "kubectl",
                          "--kubeconfig=/etc/kubernetes/admin.conf", "--namespace", "soka-heuristik"])

    def test_kind_stdin_is_forwarded_for_worker_code(self):
        with patch.object(kube, "command", return_value="ok") as call:
            kube.kubectl("exec", "-i", "rr-worker-0", "--", "python3", "-", source="print(1)")
        self.assertEqual(call.call_args.args[0][:4], ["docker", "exec", "-i", "soka-local-control-plane"])
        self.assertEqual(call.call_args.args[1], "print(1)")

    def test_end_to_end_runner_with_fake_cluster_and_real_cpu_work(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run"
            args = ["scheduler.py", "run", "--tasks", "8",
                    "--iterations-per-mi", "0.001", "--output", str(output)]
            with patch.object(sys, "argv", args), patch.object(kube, "kubectl", side_effect=self.fake_kubectl), \
                    patch("builtins.print"):
                scheduler.main()
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["mode"], "real-kubernetes-exec")
            self.assertEqual(summary["failed"], 0)
            rows = (output / "tasks.csv").read_text()
            self.assertIn("pod_uid", rows)
            self.assertIn("rr-worker-3", rows)
            topology = json.loads((output / "topology.json").read_text())
            self.assertEqual(len(topology["pods"]), 4)


if __name__ == "__main__":
    unittest.main()
