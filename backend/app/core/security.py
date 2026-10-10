"""Signed, expiring, single-use confirmation tokens: the client can approve a pending tool call
but cannot forge or alter one. bound to the user who received them."""
import base64, hashlib, hmac, json, os, secrets, time, uuid

_KEY = (os.getenv("SECRET_KEY") or secrets.token_hex(32)).encode()
_USED: dict[str, float] = {}

def _b(x: bytes) -> str: return base64.urlsafe_b64encode(x).decode().rstrip("=")
def _sig(body: str) -> str: return _b(hmac.new(_KEY, body.encode(), hashlib.sha256).digest())

def sign(call: dict, user_id: str, ttl: int = 300) -> str:
    body = _b(json.dumps({"n": uuid.uuid4().hex, "e": time.time() + ttl, "u": user_id, "c": call}).encode())
    return f"{body}.{_sig(body)}"

def verify(token: str, user_id: str) -> dict:
    try:
        body, sig = token.split(".")
        if not hmac.compare_digest(sig, _sig(body)): raise ValueError
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        raise ValueError("That confirmation isn't valid.")
    if d["u"] != user_id: raise ValueError("That confirmation isn't valid.")
    now = time.time()
    for k in [k for k, e in _USED.items() if e < now]: del _USED[k]
    if d["e"] < now: raise ValueError("That confirmation expired. Ask again.")
    if d["n"] in _USED: raise ValueError("That action was already confirmed.")
    _USED[d["n"]] = d["e"]
    return d["c"]
