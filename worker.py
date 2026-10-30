"""One real CPU task, invoked inside a Kubernetes pod using Python on stdin."""
import hashlib
import json
import sys
import time


def work(task_id, iterations):
    start = time.perf_counter()
    cpu = time.process_time()
    value = str(task_id).encode()
    for _ in range(iterations):
        value = hashlib.sha256(value).digest()
    return {"task": task_id, "iterations": iterations,
            "wall_s": time.perf_counter() - start,
            "cpu_s": time.process_time() - cpu, "digest": value.hex()}


if __name__ == "__main__":
    print(json.dumps(work(int(sys.argv[1]), int(sys.argv[2]))))
