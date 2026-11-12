# MediLink load tests

[Locust](https://locust.io) scenarios that drive the REST API the way the React
frontend does, for the three roles in a clinic's usual mix:

| Role | Weight | What it does between 1–5 s of think time |
|---|---|---|
| Patient | 6 | Dashboard, appointments, free-slot search, records, bills. Occasionally books a real slot and cancels it again (row-locked booking path + Celery queue). |
| Doctor | 3 | Dashboard, statistics, patient charts, prescriptions, labs, vitals, search. |
| Admin | 1 | Revenue and appointment statistics, invoices, payments, claims, users, AI audit log. |

The mix is about **34 reads per write**, and each simulated user makes roughly
**one request per second**. Claude-backed endpoints (`/api/ai/chat/`, briefs,
pre-checks, agent runs) are left out on purpose: they cost money per call and
are throttled to 30/hour per user.

Every simulated user on the same demo account shares one login (real people
log in once, then browse). That keeps the test from tripping the login
throttle (10/min per IP) and measuring password hashing instead of the app.

## Run it from your machine

Against Docker Compose (`docker compose up` + `seed_demo_data`):

```bash
pip install locust
cd loadtest
locust                                            # web UI on http://localhost:8089
locust --headless -u 50 -r 5 -t 3m --html reports/run.html
locust --headless -u 50 -r 5 -t 3m --exclude-tags write   # read-only
```

`locust.conf` targets the backend directly (`http://localhost:8000`). Use
`--host http://localhost:3000` to go through the frontend nginx like a browser,
or `--host http://medilink.localtest.me:8080` for the local kind cluster.

Pass/fail gates (exit code 1 when broken): `--max-fail-ratio` (default 1%) and
`--max-p95-ms` (off by default).

## Capacity test inside Kubernetes

`k8s/run.sh` runs a distributed Locust (one master, N workers) in its own
`loadtest` namespace. Workers resolve `medilink.localtest.me` to the ingress
controller, so traffic takes the real path: ingress → frontend nginx → Django.

The load follows `shape_stepped.py`: it steps up toward 100,000 users
(100, 250, 500, 750, 1,000, 1,500, 2,000, 3,000, 5,000, …), holds each step for a
minute and measures only that hold window. It stops at the first step that is
saturated (more than 5% failures, or p95 above 5 s), so the last good step is
the measured capacity of the current deployment.

```bash
cd loadtest
./k8s/run.sh                                         # 4 workers, full stepped ramp
WORKERS=6 RUN=three-backends ./k8s/run.sh            # named run, more generators
STEP_USERS=20,40 STEP_HOLD_SECONDS=20 ./k8s/run.sh   # 2-minute smoke test
kubectl delete namespace loadtest                    # remove it all afterwards
```

| Variable | Default | Meaning |
|---|---|---|
| `WORKERS` | `4` | Locust worker pods (each uses at most one core) |
| `STEP_USERS` | 100 … 100000 | Comma-separated user counts |
| `STEP_MAX_USERS` | `100000` | Drop steps above this |
| `STEP_HOLD_SECONDS` | `60` | Measured hold per step |
| `STEP_RAMP_SECONDS` | `15` | Time to ramp into each step |
| `STEP_MAX_FAIL_RATIO` | `0.05` | Stop when a step's failures exceed this |
| `STEP_MAX_P95_MS` | `5000` | Stop when a step's p95 exceeds this |

Results go to `reports/<RUN>/`: `steps.csv` (one row per step: users,
requests/s, failure ratio, p50/p95/p99, worker CPU), Locust's `report.html`,
and `cluster-cpu.log` (per-container CPU sampled from the kind node).

Scale the app between runs to see how capacity grows, e.g.
`kubectl -n medilink scale deploy/backend --replicas=3`.

### Reading the numbers

- **Worker CPU near 90%+** means the load generator, not the app, is the
  bottleneck: add `WORKERS` before trusting that step.
- A laptop runs the app *and* the generator on the same cores. Use it to find
  bottlenecks and compare changes, not to predict production capacity.
- 100,000 *simultaneous* users at ~1 request/s each is ~100,000 requests/s:
  that needs a multi-node cluster and a separate load-generation fleet. 100,000
  *registered* users is a far smaller load, since only a fraction are online at once.

## Cleaning up test bookings

Booked-then-cancelled appointments stay in the database with the reason
`[locust] load test booking`. To remove exactly those rows (their pre-visit
briefs are deleted with them):

```bash
kubectl -n medilink exec deploy/backend -- python manage.py shell -c \
  "from appointments.models import Appointment; print(Appointment.objects.filter(reason='[locust] load test booking').delete())"
```

With Docker Compose use `docker compose exec backend python manage.py shell -c "..."`.
