"""
MediLink API load test.

Simulates the three kinds of people who use MediLink, in roughly the mix a
clinic sees: mostly patients, some doctors, a few admins. Each simulated user
calls the endpoints the React frontend calls for that role's pages, with a
think time between page views. Patients occasionally book a real appointment
slot and cancel it again, which exercises the row-locked booking path and the
Celery reminder queue.

LLM-backed endpoints (/api/ai/chat/, briefs, prechecks, agent runs) are left
out on purpose: they cost money per call and are throttled to 30/hour/user.

    # UI at http://localhost:8089
    cd loadtest && locust

    # headless, with an HTML report
    cd loadtest && locust --headless -u 50 -r 5 -t 3m --html reports/run.html

    # read-only (skip booking/cancelling)
    cd loadtest && locust --exclude-tags write

See loadtest/README.md for the full guide.
"""
from __future__ import annotations

import logging
import os
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import gevent.lock
from locust import HttpUser, events, tag, task

log = logging.getLogger("medilink.loadtest")

ACCESS_COOKIE = "medilink_access"  # settings.JWT_AUTH_COOKIE
CSRF_COOKIE = "csrftoken"          # Django default CSRF_COOKIE_NAME

# Access tokens live 1h (SIMPLE_JWT.ACCESS_TOKEN_LIFETIME). Log in again a bit
# before that so long soak tests never see a 401 from expiry; any 401 that
# does show up is then a real failure.
REAUTH_AFTER_SECONDS = 50 * 60

BOOKING_REASON = "[locust] load test booking"


# ── Accounts ─────────────────────────────────────────────────────────────────
# Defaults are the accounts created by `python manage.py seed_demo_data`.
# Point the test at another environment with comma-separated user:password
# pairs, e.g.  MEDILINK_PATIENTS="pat1:secret,pat2:secret"
_DEFAULT_ACCOUNTS = {
    "patient": "patient_john:PatientPassword123!,patient_emma:PatientPassword123!",
    "doctor": "doctor_sarah:DoctorPassword123!,doctor_james:DoctorPassword123!",
    "admin": "admin:AdminPassword123!",
}


def accounts_for(role: str) -> list[tuple[str, str]]:
    raw = os.environ.get(f"MEDILINK_{role.upper()}S", _DEFAULT_ACCOUNTS[role])
    pairs = [item.split(":", 1) for item in raw.split(",") if ":" in item]
    if not pairs:
        raise ValueError(f"MEDILINK_{role.upper()}S has no user:password pairs")
    return [(user.strip(), password) for user, password in pairs]


# ── Shared logins ────────────────────────────────────────────────────────────
@dataclass
class Credentials:
    access: str
    csrf: str
    obtained_at: float = field(default_factory=time.monotonic)

    @property
    def stale(self) -> bool:
        return time.monotonic() - self.obtained_at > REAUTH_AFTER_SECONDS


class SharedLogins:
    """
    One login per account, shared by every simulated user on that account.

    Real people log in once and then browse for a long time. Logging in once per
    simulated user would trip the login throttle (LOGIN_RATE_LIMIT, 10/min per
    IP by default) and mostly measure password hashing instead of the app.
    """

    def __init__(self):
        self._creds: dict[str, Credentials] = {}
        self._locks: dict[str, gevent.lock.BoundedSemaphore] = defaultdict(gevent.lock.BoundedSemaphore)

    def get(self, client, username: str, password: str, replace: Credentials | None = None) -> Credentials:
        with self._locks[username]:
            current = self._creds.get(username)
            # Another greenlet may already have replaced the stale credentials
            # while this one was waiting for the lock.
            if current is not None and current is not replace and not current.stale:
                return current
            self._creds[username] = _login(client, username, password)
            return self._creds[username]


LOGINS = SharedLogins()


def _login(client, username: str, password: str, attempts: int = 5) -> Credentials:
    client.cookies.clear()
    for attempt in range(1, attempts + 1):
        with client.post(
            "/api/users/login/",
            json={"username": username, "password": password},
            name="/api/users/login/",
            catch_response=True,
        ) as r:
            if r.status_code == 200 and r.cookies.get(ACCESS_COOKIE):
                access = r.cookies.get(ACCESS_COOKIE)
                r.success()
                break
            if r.status_code == 429 and attempt < attempts:
                wait = float(r.headers.get("Retry-After") or 10)
                r.failure(f"login throttled, retrying in {wait:.0f}s")
                gevent.sleep(wait)
                continue
            r.failure(f"login as {username} failed: HTTP {r.status_code} {r.text[:200]}")
            raise RuntimeError(f"cannot log in as {username} (HTTP {r.status_code})")

    # The SPA fetches the CSRF cookie once at startup and echoes it back as
    # X-CSRFToken on every unsafe request (cookie auth enforces CSRF).
    r = client.get("/api/csrf/", name="/api/csrf/")
    csrf = r.cookies.get(CSRF_COOKIE) or client.cookies.get(CSRF_COOKIE)
    if not csrf:
        raise RuntimeError("GET /api/csrf/ did not set a csrftoken cookie")
    return Credentials(access=access, csrf=csrf)


# ── Helpers ──────────────────────────────────────────────────────────────────
def results(response) -> list:
    """Rows from a list endpoint, paginated ({count, results}) or not ([...])."""
    try:
        body = response.json()
    except ValueError:
        return []
    if isinstance(body, dict):
        return body.get("results", [])
    return body if isinstance(body, list) else []


class MediLinkUser(HttpUser):
    abstract = True
    role = ""

    def wait_time(self):
        opts = self.environment.parsed_options
        low = getattr(opts, "think_min", 1.0)
        high = getattr(opts, "think_max", 5.0)
        return random.uniform(low, max(low, high))

    def on_start(self):
        self.username, self._password = random.choice(accounts_for(self.role))
        self._creds: Credentials | None = None
        self._authenticate()

    def _authenticate(self):
        self._creds = LOGINS.get(self.client, self.username, self._password, replace=self._creds)
        self.client.cookies.clear()
        self.client.cookies.set(ACCESS_COOKIE, self._creds.access)
        self.client.cookies.set(CSRF_COOKIE, self._creds.csrf)
        self.client.headers["X-CSRFToken"] = self._creds.csrf
        # Django checks the Referer on unsafe requests over HTTPS.
        self.client.headers["Referer"] = self.host.rstrip("/") + "/"

    def call(self, method, path, *, name=None, ok=(200,), accept=None, **kwargs):
        """Make a request and mark it failed unless the status is expected."""
        if self._creds is None or self._creds.stale:
            self._authenticate()
        with self.client.request(method, path, name=name or path, catch_response=True, **kwargs) as r:
            if r.status_code in ok or (accept is not None and accept(r)):
                r.success()
            else:
                r.failure(f"HTTP {r.status_code}: {r.text[:200]}")
            return r

    def get(self, path, **kwargs):
        return self.call("GET", path, **kwargs)

    def post(self, path, **kwargs):
        kwargs.setdefault("ok", (200, 201))
        return self.call("POST", path, **kwargs)

    def open_detail(self, list_response, path_template):
        rows = results(list_response)
        if rows:
            row_id = random.choice(rows)["id"]
            self.get(path_template.format(id=row_id), name=path_template.format(id="[id]"))


# ── Patients ─────────────────────────────────────────────────────────────────
class PatientUser(MediLinkUser):
    role = "patient"
    weight = 6

    @task(5)
    def dashboard(self):
        self.get("/api/users/me/")
        self.get("/api/appointments/appointments/upcoming/")
        self.get("/api/ai/notifications/")

    @task(3)
    def my_appointments(self):
        r = self.get("/api/appointments/appointments/", params={"ordering": "-appointment_date"})
        self.open_detail(r, "/api/appointments/appointments/{id}/")

    @task(2)
    def find_a_slot(self):
        self._open_slots()

    @task(2)
    def medical_records(self):
        self.get("/api/medical-records/records/my_records/")

    @task(2)
    def billing(self):
        self.get("/api/billing/invoices/")
        self.get(
            "/api/billing/invoices/",
            params={"status_in": "pending,partially_paid,overdue"},
            name="/api/billing/invoices/?status_in=outstanding",
        )

    @tag("write")
    @task(1)
    def book_then_cancel(self):
        doctor, slots = self._open_slots()
        if not slots:
            return
        slot = random.choice(slots)
        r = self.post(
            "/api/appointments/appointments/",
            json={
                "doctor": doctor,
                "appointment_date": slot["date"],
                "appointment_time": slot["time"],
                "reason": BOOKING_REASON,
            },
            ok=(201,),
            # Two simulated users can pick the same free slot; the API rejecting
            # the second booking is the correct behaviour, not an error.
            accept=lambda resp: resp.status_code == 400 and "already booked" in resp.text,
        )
        if r.status_code == 201:
            self.post(
                f"/api/appointments/appointments/{r.json()['id']}/cancel/",
                name="/api/appointments/appointments/[id]/cancel/",
            )

    def _open_slots(self):
        doctors = [d["id"] for d in results(self.get("/api/users/doctors/"))]
        if not doctors:
            return None, []
        doctor = random.choice(doctors)
        # Spread bookings over two months so users rarely collide on a slot.
        start = date.today() + timedelta(days=random.randint(1, 60))
        r = self.get(
            "/api/appointments/appointments/available_slots/",
            params={"doctor": doctor, "start": start.isoformat(), "end": (start + timedelta(days=6)).isoformat()},
        )
        try:
            return doctor, r.json().get("slots", [])
        except (ValueError, AttributeError):
            return doctor, []


# ── Doctors ──────────────────────────────────────────────────────────────────
class DoctorUser(MediLinkUser):
    role = "doctor"
    weight = 3

    @task(5)
    def dashboard(self):
        self.get("/api/users/me/")
        self.get("/api/appointments/appointments/upcoming/")
        self.get("/api/appointments/appointments/statistics/")
        self.get("/api/ai/status/")
        self.get("/api/ai/notifications/")

    @task(3)
    def appointments(self):
        r = self.get("/api/appointments/appointments/", params={"ordering": "-appointment_date"})
        self.open_detail(r, "/api/appointments/appointments/{id}/")

    @task(2)
    def patients(self):
        patients = results(self.get("/api/users/patients/"))
        if patients:
            self.get(
                "/api/medical-records/records/",
                params={"patient": random.choice(patients)["id"]},
                name="/api/medical-records/records/?patient=[id]",
            )

    @task(2)
    def clinical(self):
        r = self.get("/api/medical-records/records/")
        self.open_detail(r, "/api/medical-records/records/{id}/")
        self.get("/api/medical-records/prescriptions/")
        self.get("/api/medical-records/lab-tests/")
        self.get("/api/medical-records/vital-signs/")

    @task(1)
    def search_appointments(self):
        self.get(
            "/api/appointments/appointments/",
            params={"search": random.choice(["john", "emma", "doe", "stone"])},
            name="/api/appointments/appointments/?search=[term]",
        )

    @task(1)
    def schedule(self):
        self.get("/api/appointments/schedules/")


# ── Admins ───────────────────────────────────────────────────────────────────
class AdminUser(MediLinkUser):
    role = "admin"
    weight = 1

    @task(4)
    def dashboard(self):
        self.get("/api/appointments/appointments/statistics/")
        self.get("/api/billing/invoices/statistics/")
        self.get("/api/users/")

    @task(3)
    def billing(self):
        r = self.get("/api/billing/invoices/")
        self.open_detail(r, "/api/billing/invoices/{id}/")
        self.get("/api/billing/payments/")
        self.get("/api/billing/insurance-claims/")

    @task(2)
    def people(self):
        self.get("/api/users/", params={"role": "patient"}, name="/api/users/?role=patient")
        self.get("/api/users/doctors/")

    @task(1)
    def ai_oversight(self):
        self.get("/api/ai/audit-log/")
        self.get("/api/ai/pending-actions/", params={"status": "pending"}, name="/api/ai/pending-actions/?status=pending")


# ── CLI options and pass/fail thresholds ─────────────────────────────────────
@events.init_command_line_parser.add_listener
def _add_options(parser):
    group = parser.add_argument_group("MediLink")
    group.add_argument("--think-min", type=float, default=1.0, env_var="MEDILINK_THINK_MIN",
                       help="Minimum seconds a simulated user waits between page views (default 1)")
    group.add_argument("--think-max", type=float, default=5.0, env_var="MEDILINK_THINK_MAX",
                       help="Maximum seconds a simulated user waits between page views (default 5)")
    group.add_argument("--max-fail-ratio", type=float, default=0.01, env_var="MEDILINK_MAX_FAIL_RATIO",
                       help="Exit 1 if more than this fraction of requests failed (default 0.01)")
    group.add_argument("--max-p95-ms", type=float, default=0, env_var="MEDILINK_MAX_P95_MS",
                       help="Exit 1 if the overall 95th percentile exceeds this many ms (0 = off)")


@events.quitting.add_listener
def _enforce_thresholds(environment, **_kwargs):
    opts = environment.parsed_options
    total = environment.stats.total
    if opts is None or total.num_requests == 0:  # library use, or a distributed worker
        return
    p95 = total.get_response_time_percentile(0.95)
    problems = []
    if total.fail_ratio > opts.max_fail_ratio:
        problems.append(f"fail ratio {total.fail_ratio:.2%} > {opts.max_fail_ratio:.2%}")
    if opts.max_p95_ms and p95 > opts.max_p95_ms:
        problems.append(f"p95 {p95:.0f} ms > {opts.max_p95_ms:.0f} ms")
    if problems:
        log.error("Thresholds FAILED: %s", "; ".join(problems))
        environment.process_exit_code = 1
    else:
        log.info("Thresholds passed: fail ratio %.2f%%, p95 %.0f ms", total.fail_ratio * 100, p95)
