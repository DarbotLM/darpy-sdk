"""Bounded, protocol-neutral execution for application-provided async handlers."""

import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal, NoReturn
from uuid import uuid4

import anyio
from anyio import current_time
from anyio.lowlevel import checkpoint_if_cancelled, current_token

ProtocolName = Literal["local", "mcp", "acp", "activity"]
_PROTOCOLS = ("local", "mcp", "acp", "activity")


def _require_text(value: object, name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    if nonempty and not value.strip():
        raise ValueError(f"{name} must be nonempty")
    return value


def _require_protocol(value: object) -> None:
    _require_text(value, "protocol")
    if value not in _PROTOCOLS:
        raise ValueError("Unknown task protocol")


def _require_positive_integer(value: object, name: str) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer")


def _require_finite(value: object, name: str, *, allow_zero: bool = False) -> None:
    message = f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}"
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise ValueError(message)
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(message)


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def _json_constant(value: str) -> NoReturn:
    raise ValueError(f"Nonfinite JSON number: {value}")


def _json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite JSON number")
    return number


def _require_payload(value: object) -> None:
    text = _require_text(value, "payload_json", nonempty=False)
    try:
        payload = json.loads(
            text, object_pairs_hook=_json_pairs, parse_constant=_json_constant, parse_float=_json_float
        )
    except ValueError as exc:
        raise ValueError("payload_json must contain a finite JSON object with unique keys") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload_json must contain a JSON object")


@dataclass(frozen=True)
class Task:
    """Immutable SDK adapter context, not an authorization credential.

    ``payload_json`` must encode a finite JSON object with unique keys. This
    object-envelope contract preserves protocol content and metadata; it is
    deliberately narrower than the platform's general JSON payload contract.
    Sessions correlate requests inside the host's authenticated scope. ``cwd``
    is descriptive context and never changes the process working directory.
    """

    prompt: str
    session_id: str
    protocol: ProtocolName = "local"
    cwd: str | None = None
    payload_json: str | None = None
    request_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self) -> None:
        _require_text(self.prompt, "prompt", nonempty=False)
        _require_text(self.session_id, "session_id")
        _require_text(self.request_id, "request_id")
        _require_protocol(self.protocol)
        if self.cwd is not None:
            _require_text(self.cwd, "cwd")
        if self.payload_json is not None:
            _require_payload(self.payload_json)


@dataclass(frozen=True)
class RunBudget:
    """Cooperative deadline and Unicode character limits, not token or byte limits.

    The deadline includes time queued for this runtime's concurrency slot.
    Input size counts every string in the task context, including identifiers,
    protocol, working-directory context, and the serialized payload. Output size
    is checked after the handler returns and cannot prevent output allocation.
    """

    timeout_seconds: float = 60.0
    max_input_chars: int = 1_000_000
    max_output_chars: int = 1_000_000

    def __post_init__(self) -> None:
        _require_finite(self.timeout_seconds, "timeout_seconds")
        _require_positive_integer(self.max_input_chars, "max_input_chars")
        _require_positive_integer(self.max_output_chars, "max_output_chars")


@dataclass(frozen=True)
class RunResult:
    """Successful handler output and timing, without a correctness claim."""

    request_id: str
    session_id: str
    protocol: ProtocolName
    text: str
    elapsed_seconds: float

    def __post_init__(self) -> None:
        _require_text(self.request_id, "request_id")
        _require_text(self.session_id, "session_id")
        _require_protocol(self.protocol)
        _require_text(self.text, "text", nonempty=False)
        _require_finite(self.elapsed_seconds, "elapsed_seconds", allow_zero=True)


class BudgetExceededError(RuntimeError):
    """An input, output, or execution-time budget was exceeded."""


Handler = Callable[[Task], Awaitable[str]]


def _require_output(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Runtime handlers must return text")
    return value


class Runtime:
    """Execute a handler with bounded active concurrency on one event loop.

    Handlers must yield and honor cancellation. Deadlines reject late results,
    but cannot preempt blocking code or bound cleanup duration. This is not a
    sandbox, process isolation, or a bound on pending callers. Caller
    cancellation propagates; handler failures are never retried automatically.
    The runtime binds to the first event loop on which ``run`` is called.
    """

    def __init__(self, handler: Handler, *, budget: RunBudget | None = None, max_concurrency: int = 4) -> None:
        _require_positive_integer(max_concurrency, "max_concurrency")
        self.handler = handler
        self.budget = budget if budget is not None else RunBudget()
        self._slots = anyio.Semaphore(max_concurrency)
        self._loop_token: object | None = None

    async def run(self, task: Task) -> RunResult:
        """Return a successful receipt or propagate handler failure/cancellation.

        Raises:
            BudgetExceededError: Input, output, or execution time exceeds its budget.
            RuntimeError: The runtime was previously used on another event loop.
        """
        token = current_token()
        if self._loop_token is not None and self._loop_token != token:
            raise RuntimeError("A runtime belongs to one event loop")
        self._loop_token = token
        input_size = sum(
            len(value)
            for value in (
                task.prompt,
                task.session_id,
                task.protocol,
                task.cwd or "",
                task.payload_json or "",
                task.request_id,
            )
        )
        if input_size > self.budget.max_input_chars:
            raise BudgetExceededError("Input character budget exceeded")
        started = current_time()
        output: object = None
        with anyio.move_on_after(self.budget.timeout_seconds) as scope:
            async with self._slots:
                output = await self.handler(task)
            # A handler can catch cancellation. Re-observe cancellation before
            # accepting its result, including cancellation from an outer scope.
            await checkpoint_if_cancelled()
        if scope.cancel_called or current_time() >= scope.deadline:
            raise BudgetExceededError("Execution time budget exceeded")
        text = _require_output(output)
        if len(text) > self.budget.max_output_chars:
            raise BudgetExceededError("Output character budget exceeded")
        return RunResult(task.request_id, task.session_id, task.protocol, text, current_time() - started)
