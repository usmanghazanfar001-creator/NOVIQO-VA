"""Tool registry. A tool is an async fn(args, ctx) -> JSON-able. ctx: {"tz", "actions", "pending", "confirmed"}.
ctx["actions"] carries instructions for the client (start a timer, open a URL).
confirm: optional fn(args) -> str. If set, the tool never runs straight from the model: the user must approve
the returned summary on screen first. The fn may raise ValueError to reject bad args before asking."""
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

@dataclass
class Tool:
    name: str
    description: str
    schema: dict
    fn: Callable[[dict, dict], Awaitable[Any]]
    confirm: Callable[[dict], str] | None = None
    voice_ok: bool = False   # may the user approve this by saying "yes"? (low-risk tools only)

REGISTRY: dict[str, Tool] = {}

def tool(name: str, description: str, props: dict, required: tuple = (), confirm=None, voice_ok: bool = False):
    def deco(fn):
        REGISTRY[name] = Tool(name, description, {"type": "object", "properties": props, "required": list(required)}, fn, confirm, voice_ok)
        return fn
    return deco
