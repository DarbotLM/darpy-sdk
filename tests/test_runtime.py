from dataclasses import asdict, replace
from typing import cast

import anyio
import pytest
from dirty_equals import IsFloat
from inline_snapshot import snapshot

import darpy_sdk.runtime as runtime_module
from darpy_sdk.runtime import BudgetExceededError, ProtocolName, RunBudget, RunResult, Runtime, Task


@pytest.fixture(scope="module", autouse=True)
def _module_runner_lease() -> None:
    """Use one backend runner per test instead of the suite's shared asyncio lease."""


@pytest.fixture(params=["asyncio", "trio"])
def anyio_backend(request: pytest.FixtureRequest) -> str:
    assert isinstance(request.param, str)
    return request.param


@pytest.mark.anyio
async def test_runtime_limits_interleaved_handlers_and_returns_complete_receipts() -> None:
    """The SDK bounds active handlers and preserves request context in successful receipts."""
    both_started, release = anyio.Event(), anyio.Event()
    active, maximum = 0, 0
    tasks = {
        str(index): Task(
            prompt, "session", protocol="acp", cwd="/workspace", payload_json='{"number":0.5}', request_id=str(index)
        )
        for index, prompt in enumerate(["one", "two", "three", "four"])
    }

    async def handler(task: Task) -> str:
        nonlocal active, maximum
        assert task is tasks[task.request_id]
        active += 1
        maximum = max(active, maximum)
        if active == 2:
            both_started.set()
        try:
            await release.wait()
            return task.prompt.upper()
        finally:
            active -= 1

    runtime = Runtime(handler, max_concurrency=2)
    results: dict[str, RunResult] = {}

    async def execute(task: Task) -> None:
        results[task.request_id] = await runtime.run(task)

    with anyio.fail_after(5):
        async with anyio.create_task_group() as group:
            for task in tasks.values():
                group.start_soon(execute, task)
            await both_started.wait()
            assert active == 2
            release.set()
    assert (maximum, active) == (2, 0)
    receipts = [asdict(results[key]) for key in sorted(results)]
    for receipt in receipts:
        assert isinstance(receipt["elapsed_seconds"], float)
        receipt["elapsed_seconds"] = IsFloat
    assert receipts == snapshot(
        [
            {"request_id": "0", "session_id": "session", "protocol": "acp", "text": "ONE", "elapsed_seconds": IsFloat},
            {"request_id": "1", "session_id": "session", "protocol": "acp", "text": "TWO", "elapsed_seconds": IsFloat},
            {
                "request_id": "2",
                "session_id": "session",
                "protocol": "acp",
                "text": "THREE",
                "elapsed_seconds": IsFloat,
            },
            {"request_id": "3", "session_id": "session", "protocol": "acp", "text": "FOUR", "elapsed_seconds": IsFloat},
        ]
    )


@pytest.mark.anyio
async def test_runtime_deadline_includes_queue_and_rejects_late_handler_return() -> None:
    """The SDK charges queue time and rejects results from cancellation-shielded handlers that finish late."""
    entered, release = anyio.Event(), anyio.Event()
    calls: list[str] = []
    failures: dict[str, str] = {}

    async def handler(task: Task) -> str:
        assert task.request_id == "held"
        calls.append(task.request_id)
        entered.set()
        with anyio.CancelScope(shield=True):
            await release.wait()
        return "late output"

    # A short deadline is the feature being exercised, not an ordering primitive.
    runtime = Runtime(handler, budget=RunBudget(timeout_seconds=0.01), max_concurrency=1)

    async def hold_slot() -> None:
        with pytest.raises(BudgetExceededError) as error:
            await runtime.run(Task("hold", "s", request_id="held"))
        failures["held"] = str(error.value)

    with anyio.fail_after(5):
        async with anyio.create_task_group() as group:
            group.start_soon(hold_slot)
            await entered.wait()
            try:
                with pytest.raises(BudgetExceededError) as error:
                    await runtime.run(Task("queued", "s", request_id="queued"))
                failures["queued"] = str(error.value)
            finally:
                release.set()
    assert calls == ["held"]
    assert failures == snapshot({"queued": "Execution time budget exceeded", "held": "Execution time budget exceeded"})


@pytest.mark.anyio
async def test_runtime_preserves_handler_timeout_error_identity() -> None:
    """A handler's own timeout remains its failure, distinct from an SDK execution-budget failure."""
    failure = TimeoutError("provider deadline")

    async def handler(task: Task) -> str:
        assert task.prompt == "request"
        raise failure

    with pytest.raises(TimeoutError) as error:
        await Runtime(handler).run(Task("request", "session"))
    assert error.value is failure


@pytest.mark.anyio
@pytest.mark.parametrize("swallow", [False, True])
async def test_runtime_propagates_caller_cancellation_after_handler_cleanup(swallow: bool) -> None:
    """The SDK cannot report success after caller cancellation, even if a handler catches that cancellation."""
    entered, finished = anyio.Event(), anyio.Event()
    history: list[str] = []
    scopes: list[anyio.CancelScope] = []
    send, receive = anyio.create_memory_object_stream[str]()

    async def handler(task: Task) -> str:
        assert task.prompt == "request"
        entered.set()
        try:
            return await receive.receive()
        except anyio.get_cancelled_exc_class():
            history.append("cancelled")
            if swallow:
                return "ignored cancellation"
            raise
        finally:
            history.append("cleaned")

    runtime = Runtime(handler)

    async def caller() -> None:
        with anyio.CancelScope() as scope:
            scopes.append(scope)
            await runtime.run(Task("request", "session"))
        finished.set()

    with send, receive, anyio.fail_after(5):
        async with anyio.create_task_group() as group:
            group.start_soon(caller)
            await entered.wait()
            scopes[0].cancel()
            await finished.wait()
    assert scopes[0].cancelled_caught
    assert history == snapshot(["cancelled", "cleaned"])


def test_task_rejects_invalid_context_and_ambiguous_json_envelopes() -> None:
    """The SDK's object-envelope contract rejects invalid context before a handler can receive it."""
    cases: list[tuple[str, str, object]] = [
        ("prompt_type", "prompt", False),
        ("session_blank", "session_id", " "),
        ("request_blank", "request_id", ""),
        ("protocol_unknown", "protocol", "http"),
        ("protocol_type", "protocol", []),
        ("cwd_type", "cwd", 4),
        ("cwd_blank", "cwd", " "),
        ("payload_type", "payload_json", {}),
        ("payload_syntax", "payload_json", "{"),
        ("payload_array", "payload_json", "[]"),
        ("payload_null", "payload_json", "null"),
        ("payload_nan", "payload_json", '{"value":NaN}'),
        ("payload_overflow", "payload_json", '{"value":1e9999}'),
        ("payload_duplicate", "payload_json", '{"key":1,"key":2}'),
    ]
    failures: dict[str, str] = {}
    for label, field, value in cases:
        values: dict[str, object] = {
            "prompt": "request",
            "session_id": "session",
            "request_id": "request",
            "protocol": "local",
            "cwd": None,
            "payload_json": None,
        }
        values[field] = value
        with pytest.raises(ValueError) as error:
            Task(
                prompt=cast(str, values["prompt"]),
                session_id=cast(str, values["session_id"]),
                request_id=cast(str, values["request_id"]),
                protocol=cast(ProtocolName, values["protocol"]),
                cwd=cast(str | None, values["cwd"]),
                payload_json=cast(str | None, values["payload_json"]),
            )
        failures[label] = str(error.value)
    assert failures == snapshot(
        {
            "prompt_type": "prompt must be text",
            "session_blank": "session_id must be nonempty",
            "request_blank": "request_id must be nonempty",
            "protocol_unknown": "Unknown task protocol",
            "protocol_type": "protocol must be text",
            "cwd_type": "cwd must be text",
            "cwd_blank": "cwd must be nonempty",
            "payload_type": "payload_json must be text",
            "payload_syntax": "payload_json must contain a finite JSON object with unique keys",
            "payload_array": "payload_json must contain a JSON object",
            "payload_null": "payload_json must contain a JSON object",
            "payload_nan": "payload_json must contain a finite JSON object with unique keys",
            "payload_overflow": "payload_json must contain a finite JSON object with unique keys",
            "payload_duplicate": "payload_json must contain a finite JSON object with unique keys",
        }
    )


def test_budget_and_concurrency_reject_invalid_numeric_limits() -> None:
    """SDK limits reject booleans, nonfinite numbers, invalid ranges, and noninteger character/concurrency limits."""
    failures: dict[str, str] = {}
    budget = RunBudget(timeout_seconds=1)

    async def handler(task: Task) -> str:
        raise NotImplementedError

    timeout_cases: list[tuple[str, object]] = [
        ("boolean", True),
        ("text", "1"),
        ("zero", 0),
        ("negative", -1),
        ("nan", float("nan")),
        ("infinity", float("inf")),
        ("overflow", 10**1000),
    ]
    for label, value in timeout_cases:
        with pytest.raises(ValueError) as error:
            replace(budget, timeout_seconds=value)
        failures[f"timeout:{label}"] = str(error.value)
    for field in ("max_input_chars", "max_output_chars", "max_concurrency"):
        for label, value in [("boolean", True), ("zero", 0), ("negative", -1), ("fraction", 1.5)]:
            with pytest.raises(ValueError) as error:
                if field == "max_concurrency":
                    Runtime(handler, max_concurrency=cast(int, value))
                else:
                    replace(budget, **{field: value})
            failures[f"{field}:{label}"] = str(error.value)
    assert failures == snapshot(
        {
            "timeout:boolean": "timeout_seconds must be finite and positive",
            "timeout:text": "timeout_seconds must be finite and positive",
            "timeout:zero": "timeout_seconds must be finite and positive",
            "timeout:negative": "timeout_seconds must be finite and positive",
            "timeout:nan": "timeout_seconds must be finite and positive",
            "timeout:infinity": "timeout_seconds must be finite and positive",
            "timeout:overflow": "timeout_seconds must be finite and positive",
            "max_input_chars:boolean": "max_input_chars must be a positive integer",
            "max_input_chars:zero": "max_input_chars must be a positive integer",
            "max_input_chars:negative": "max_input_chars must be a positive integer",
            "max_input_chars:fraction": "max_input_chars must be a positive integer",
            "max_output_chars:boolean": "max_output_chars must be a positive integer",
            "max_output_chars:zero": "max_output_chars must be a positive integer",
            "max_output_chars:negative": "max_output_chars must be a positive integer",
            "max_output_chars:fraction": "max_output_chars must be a positive integer",
            "max_concurrency:boolean": "max_concurrency must be a positive integer",
            "max_concurrency:zero": "max_concurrency must be a positive integer",
            "max_concurrency:negative": "max_concurrency must be a positive integer",
            "max_concurrency:fraction": "max_concurrency must be a positive integer",
        }
    )


@pytest.mark.anyio
async def test_input_budget_counts_all_context_and_accepts_exact_unicode_boundary() -> None:
    """The SDK charges every task string before execution and counts Unicode characters rather than encoded bytes."""
    received: list[Task] = []

    async def handler(task: Task) -> str:
        received.append(task)
        return task.prompt

    runtime = Runtime(handler, budget=RunBudget(max_input_chars=8))
    task = Task("🙂", "s", request_id="r")
    assert (await runtime.run(task)).text == task.prompt
    failures: dict[str, str] = {}
    variants = {
        "prompt": replace(task, prompt="🙂x"),
        "session_id": replace(task, session_id="sx"),
        "request_id": replace(task, request_id="rx"),
        "protocol": replace(task, protocol="activity"),
        "cwd": replace(task, cwd="x"),
        "payload_json": replace(task, payload_json="{}"),
    }
    for field, variant in variants.items():
        with pytest.raises(BudgetExceededError) as error:
            await runtime.run(variant)
        failures[field] = str(error.value)
    assert len(received) == 1
    assert received[0] is task
    assert failures == snapshot(
        {
            "prompt": "Input character budget exceeded",
            "session_id": "Input character budget exceeded",
            "request_id": "Input character budget exceeded",
            "protocol": "Input character budget exceeded",
            "cwd": "Input character budget exceeded",
            "payload_json": "Input character budget exceeded",
        }
    )


@pytest.mark.anyio
async def test_output_contract_accepts_unicode_boundary_and_rejects_oversize_or_nontext() -> None:
    """The SDK validates handler output as text and applies its character budget after execution."""
    output: str | int = "🙂"

    async def handler(task: Task) -> str:
        assert task.prompt == "output"
        return cast(str, output)

    runtime = Runtime(handler, budget=RunBudget(max_output_chars=1))
    task = Task("output", "session")
    assert (await runtime.run(task)).text == output
    failures: dict[str, tuple[str, str]] = {}
    for label, output in [("nontext", 5), ("oversized", "🙂x")]:
        with pytest.raises((TypeError, BudgetExceededError)) as error:
            await runtime.run(task)
        failures[label] = (type(error.value).__name__, str(error.value))
    assert failures == snapshot(
        {
            "nontext": ("TypeError", "Runtime handlers must return text"),
            "oversized": ("BudgetExceededError", "Output character budget exceeded"),
        }
    )


def test_runtime_refuses_reuse_from_a_different_event_loop(anyio_backend: str) -> None:
    """The SDK binds a runtime to its first loop even when successive loops use the same AnyIO backend."""
    task = Task("request", "session")

    async def handler(received: Task) -> str:
        assert received is task
        return received.prompt

    runtime = Runtime(handler)

    async def execute() -> RunResult:
        return await runtime.run(task)

    assert anyio.run(execute, backend=anyio_backend).text == task.prompt
    with pytest.raises(RuntimeError) as error:
        anyio.run(execute, backend=anyio_backend)
    assert str(error.value) == snapshot("A runtime belongs to one event loop")


def test_result_contract_accepts_zero_elapsed_and_rejects_invalid_receipts() -> None:
    """SDK receipts permit empty output and zero elapsed time while validating their identities and finite duration."""
    result = RunResult("request", "session", "local", "", 0.0)
    assert asdict(result) == snapshot(
        {"request_id": "request", "session_id": "session", "protocol": "local", "text": "", "elapsed_seconds": 0.0}
    )
    cases: list[tuple[str, str, object]] = [
        ("request_blank", "request_id", " "),
        ("session_type", "session_id", 1),
        ("protocol_unknown", "protocol", "unknown"),
        ("output_type", "text", None),
        ("elapsed_negative", "elapsed_seconds", -1),
        ("elapsed_boolean", "elapsed_seconds", False),
        ("elapsed_nan", "elapsed_seconds", float("nan")),
        ("elapsed_infinity", "elapsed_seconds", float("inf")),
    ]
    failures: dict[str, str] = {}
    for label, field, value in cases:
        with pytest.raises(ValueError) as error:
            replace(result, **{field: value})
        failures[label] = str(error.value)
    assert failures == snapshot(
        {
            "request_blank": "request_id must be nonempty",
            "session_type": "session_id must be text",
            "protocol_unknown": "Unknown task protocol",
            "output_type": "text must be text",
            "elapsed_negative": "elapsed_seconds must be finite and nonnegative",
            "elapsed_boolean": "elapsed_seconds must be finite and nonnegative",
            "elapsed_nan": "elapsed_seconds must be finite and nonnegative",
            "elapsed_infinity": "elapsed_seconds must be finite and nonnegative",
        }
    )


@pytest.mark.anyio
async def test_runtime_rejects_expired_result_before_timeout_callback_can_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The SDK checks time after a non-yielding handler returns, even when the loop has not delivered cancellation."""
    budget = RunBudget()

    async def handler(task: Task) -> str:
        assert task.prompt == "non-yielding"
        expired_time = anyio.current_time() + budget.timeout_seconds + 1.0
        monkeypatch.setattr(runtime_module, "current_time", lambda: expired_time)
        return "late result"

    with pytest.raises(BudgetExceededError) as error:
        await Runtime(handler, budget=budget).run(Task("non-yielding", "session"))
    assert str(error.value) == snapshot("Execution time budget exceeded")
