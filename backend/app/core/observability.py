"""Structured logs, request ids, Prometheus metrics, security headers, optional Sentry.
Logs contain method, route template, status and timing only: never query strings, bodies, cookies or user content."""
import contextvars, hmac, json, logging, os, re, sys, time, uuid
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

request_id = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger("noviqo.request")
REQS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
LAT = Histogram("http_request_seconds", "HTTP latency in seconds", ["route"])
TOOLS = Counter("tool_calls_total", "Agent tool calls", ["tool", "outcome"])
_RID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

class JsonFormatter(logging.Formatter):
    def format(self, r):
        d = {"ts": self.formatTime(r, "%Y-%m-%dT%H:%M:%S"), "level": r.levelname, "logger": r.name,
             "msg": r.getMessage(), "request_id": request_id.get()}
        if r.exc_info: d["exc"] = self.formatException(r.exc_info)
        return json.dumps(d, default=str)

def setup_logging():
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter() if os.getenv("ENV") == "production" else logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger(); root.handlers = [h]; root.setLevel(os.getenv("LOG_LEVEL", "INFO"))
    for noisy in ("httpx", "httpcore"): logging.getLogger(noisy).setLevel(logging.WARNING)  # they log full URLs (OAuth tokens)

def scrub(event, hint):
    req = event.get("request", {})
    for k in ("cookies", "headers", "data", "query_string"): req.pop(k, None)
    return event

def init_sentry():
    if os.getenv("SENTRY_DSN"):
        import sentry_sdk
        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], send_default_pii=False, traces_sample_rate=0.0, before_send=scrub)

def install(app: FastAPI):
    hsts = os.getenv("COOKIE_SECURE") == "true"

    @app.middleware("http")
    async def observe(request: Request, call_next):
        rid = request.headers.get("x-request-id", ""); rid = rid if _RID.match(rid) else uuid.uuid4().hex[:16]
        token, t0 = request_id.set(rid), time.perf_counter()
        try: resp = await call_next(request)
        except Exception:
            log.exception("unhandled error"); resp = JSONResponse({"error": "Something went wrong on the server."}, 500)
        dt = time.perf_counter() - t0
        route = getattr(request.scope.get("route"), "path", "unmatched")   # template, so ids never reach logs or metrics
        REQS.labels(request.method, route, resp.status_code).inc(); LAT.labels(route).observe(dt)
        log.info("%s %s %s %.0fms", request.method, route, resp.status_code, dt * 1000)
        h = resp.headers
        h["X-Request-ID"], h["X-Content-Type-Options"], h["X-Frame-Options"] = rid, "nosniff", "DENY"
        h["Referrer-Policy"], h["Cache-Control"] = "no-referrer", "no-store"
        if hsts: h["Strict-Transport-Security"] = "max-age=31536000"
        request_id.reset(token); return resp

    @app.get("/metrics", include_in_schema=False)   # not proxied by Caddy: scrape it from inside the network
    async def metrics(request: Request):
        want = os.getenv("METRICS_TOKEN")
        if not want: return Response(status_code=404)
        if not hmac.compare_digest(request.headers.get("authorization", "").removeprefix("Bearer ").encode(), want.encode()):
            return Response(status_code=401)
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
