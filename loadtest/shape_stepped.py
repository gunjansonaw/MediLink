"""
Stepped capacity test: ramp toward a target user count (default 100,000) one
step at a time, measure each step on its own, and stop at the first step where
the system is saturated.

Use it together with the normal locustfile, which supplies the user mix:

    locust -f locustfile.py,shape_stepped.py --headless

Every step ramps to its user count, then holds it for STEP_HOLD_SECONDS. Only
the hold window is measured (throughput, failures, p50/p95/p99), so ramp-up
noise never leaks into a step's numbers. The run stops after the first step
whose hold window breaks a limit:

    STEP_MAX_FAIL_RATIO  fraction of failed requests   (default 0.05)
    STEP_MAX_P95_MS      95th percentile response time (default 5000)

The per-step table is logged as each step finishes and written to
STEP_REPORT (CSV) when the run ends.
"""
from __future__ import annotations

import csv
import logging
import os

from locust import LoadTestShape, events

log = logging.getLogger("medilink.stepped")

DEFAULT_STEPS = "100,250,500,750,1000,1500,2000,3000,5000,7500,10000,15000,25000,50000,100000"


def _percentile(histogram: dict, total: int, fraction: float) -> float:
    """Percentile from Locust's rounded response-time histogram {ms: count}."""
    if total <= 0:
        return 0.0
    target = total * fraction
    seen = 0
    for ms in sorted(histogram):
        seen += histogram[ms]
        if seen >= target:
            return float(ms)
    return float(max(histogram))


class SteppedRamp(LoadTestShape):
    steps = [int(s) for s in os.environ.get("STEP_USERS", DEFAULT_STEPS).split(",") if s.strip()]
    max_users = int(os.environ.get("STEP_MAX_USERS", 100_000))
    hold = float(os.environ.get("STEP_HOLD_SECONDS", 60))
    ramp = float(os.environ.get("STEP_RAMP_SECONDS", 15))
    max_fail_ratio = float(os.environ.get("STEP_MAX_FAIL_RATIO", 0.05))
    max_p95_ms = float(os.environ.get("STEP_MAX_P95_MS", 5000))

    def __init__(self):
        super().__init__()
        self.steps = [s for s in self.steps if s <= self.max_users]
        self.index = 0
        self.step_started = 0.0
        self.hold_started: float | None = None
        self.snapshot = None
        self.prev_users = 0
        self.max_worker_cpu = 0.0
        self.results: list[dict] = []
        self.stopped_because = "reached the last step"

    # Locust calls tick() about once a second on the master
    def tick(self):
        now = self.get_run_time()
        if self.index >= len(self.steps):
            return None

        users = self.steps[self.index]
        spawn_rate = max(10.0, (users - self.prev_users) / self.ramp)
        self._track_worker_cpu()

        ramp_done_at = self.step_started + max(self.ramp, (users - self.prev_users) / spawn_rate) + 5
        if self.hold_started is None and now >= ramp_done_at:
            self.hold_started = now
            self.snapshot = self._take_snapshot()
            self.max_worker_cpu = 0.0

        if self.hold_started is not None and now >= self.hold_started + self.hold:
            row = self._finish_step(users, now - self.hold_started)
            saturated = []
            if row["fail_ratio"] > self.max_fail_ratio:
                saturated.append(f"failures {row['fail_ratio']:.1%} > {self.max_fail_ratio:.0%}")
            if row["p95_ms"] > self.max_p95_ms:
                saturated.append(f"p95 {row['p95_ms']:.0f} ms > {self.max_p95_ms:.0f} ms")
            if saturated:
                self.stopped_because = f"saturated at {users} users ({'; '.join(saturated)})"
                log.warning("STOP: %s", self.stopped_because)
                self.index = len(self.steps)
                return None
            self.prev_users = users
            self.index += 1
            self.step_started = now
            self.hold_started = None
            if self.index >= len(self.steps):
                return None
            users = self.steps[self.index]
            spawn_rate = max(10.0, (users - self.prev_users) / self.ramp)

        return users, spawn_rate

    def _track_worker_cpu(self):
        workers = getattr(self.runner, "clients", None) or getattr(self.runner, "workers", None) or {}
        for worker in getattr(workers, "values", lambda: [])():
            self.max_worker_cpu = max(self.max_worker_cpu, float(getattr(worker, "cpu_usage", 0) or 0))

    def _take_snapshot(self):
        total = self.runner.stats.total
        return {
            "requests": total.num_requests,
            "failures": total.num_failures,
            "histogram": dict(total.response_times),
        }

    def _finish_step(self, users: int, seconds: float) -> dict:
        total = self.runner.stats.total
        before = self.snapshot
        requests = total.num_requests - before["requests"]
        failures = total.num_failures - before["failures"]
        window = {
            ms: count - before["histogram"].get(ms, 0)
            for ms, count in total.response_times.items()
            if count - before["histogram"].get(ms, 0) > 0
        }
        counted = sum(window.values())
        row = {
            "users": users,
            "active_users": self.runner.user_count,
            "seconds": round(seconds, 1),
            "requests": requests,
            "rps": round(requests / seconds, 1) if seconds else 0.0,
            "fail_ratio": round(failures / requests, 4) if requests else 0.0,
            "p50_ms": _percentile(window, counted, 0.50),
            "p95_ms": _percentile(window, counted, 0.95),
            "p99_ms": _percentile(window, counted, 0.99),
            "max_worker_cpu": round(self.max_worker_cpu, 1),
        }
        self.results.append(row)
        log.info(
            "STEP users=%(users)d active=%(active_users)d rps=%(rps).1f fail=%(fail_ratio).2f%% "
            "p50=%(p50_ms).0fms p95=%(p95_ms).0fms p99=%(p99_ms).0fms worker_cpu=%(max_worker_cpu).0f%%",
            {**row, "fail_ratio": row["fail_ratio"] * 100},
        )
        return row


@events.quitting.add_listener
def _write_step_report(environment, **_kwargs):
    shape = environment.shape_class
    if not isinstance(shape, SteppedRamp) or not shape.results:
        return
    path = os.environ.get("STEP_REPORT", "reports/steps.csv")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(shape.results[0]))
        writer.writeheader()
        writer.writerows(shape.results)
    log.info("Stepped run finished: %s. Step table written to %s", shape.stopped_because, path)
