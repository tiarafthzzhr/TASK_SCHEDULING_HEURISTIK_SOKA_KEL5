import os
import unittest
from unittest.mock import patch

import kube_backend as kube
from scripts.submit_experiment import job
import test_kubernetes as fixtures


class K3sTests(unittest.TestCase):
    def test_two_node_profile_allows_work_on_control_plane(self):
        fixture = fixtures.KubernetesTests()
        fixture.setUp()
        fixture.nodes[0]["metadata"]["labels"]["node-role.kubernetes.io/control-plane"] = "true"
        with patch.object(kube, "MODE", "k3s"), patch.object(kube, "kubectl", side_effect=fixture.fake_kubectl):
            evidence = kube.verify(fixture.data)
        self.assertEqual(evidence["mode"], "k3s-two-laptop-lab")
        report = kube.format_report({"tasks": 0, "failed": 0, "makespan_s": 1,
                                     "average_wait_s": 0, "task_cpu_utilization_pct": 0,
                                     "iterations_per_mi": 10}, evidence, [], ".")
        self.assertIn("2 node K3s", report)
        self.assertNotIn("control-plane tambahan", report)

    def test_in_cluster_uses_service_account_without_host_context(self):
        with patch.object(kube, "MODE", "k3s"), patch.dict(os.environ, {
                "SOKA_IN_CLUSTER": "1", "KUBERNETES_SERVICE_HOST": "10.43.0.1"}), \
                patch.object(kube, "command", return_value="{}") as called:
            kube.kubectl("get", "nodes")
        self.assertNotIn("--context", called.call_args.args[0])

    def test_job_is_batch_has_correct_dataset_and_output_volume(self):
        resource = job(1000)
        spec = resource["spec"]["template"]["spec"]
        self.assertEqual(resource["kind"], "Job")
        self.assertEqual(resource["spec"]["backoffLimit"], 0)
        self.assertEqual(spec["nodeSelector"], {"soka.lab/host": "host1"})
        container = spec["containers"][0]
        self.assertEqual(container["args"], ["run", "--dataset-size", "1000"])
        self.assertEqual(container["imagePullPolicy"], "Never")
        self.assertIn({"name": "SOKA_IN_CLUSTER", "value": "1"}, container["env"])
        self.assertEqual(spec["volumes"][0]["persistentVolumeClaim"]["claimName"], "rr-results")
        self.assertNotEqual(resource["metadata"]["name"], job(1000)["metadata"]["name"])


if __name__ == "__main__":
    unittest.main()
