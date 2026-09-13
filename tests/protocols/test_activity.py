"""DARPy Activity boundaries and the official Microsoft Agents turn pipeline."""

import json
from collections.abc import Awaitable, Callable
from dataclasses import FrozenInstanceError
from datetime import datetime, tzinfo

import pytest
from inline_snapshot import snapshot
from microsoft_agents.activity import Activity, ConversationReference, ResourceResponse
from microsoft_agents.activity import activity as activity_module
from microsoft_agents.hosting.core import ChannelAdapter, TurnContext
from microsoft_agents.hosting.core.authorization import ClaimsIdentity
from pydantic import JsonValue, ValidationError

from darpy_sdk.protocols.activity import ActivityEnvelope, ActivityHandler
from darpy_sdk.protocols.activity_hosting import handle_turn
from darpy_sdk.runtime import Runtime, Task


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> "FixedDatetime":
        return cls(2026, 1, 1, tzinfo=tz)


class RecordingAdapter(ChannelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.sent: list[Activity] = []
        self.responses = [ResourceResponse(id="outgoing-1")]

    async def send_activities(self, context: TurnContext, activities: list[Activity]) -> list[ResourceResponse]:
        self.sent.extend(activities)
        return self.responses

    async def update_activity(self, context: TurnContext, activity: Activity) -> None:
        raise NotImplementedError

    async def delete_activity(self, context: TurnContext, reference: ConversationReference) -> None:
        raise NotImplementedError


@pytest.fixture
def incoming() -> dict[str, JsonValue]:
    return {
        "type": "message",
        "id": "inbound-1",
        "serviceUrl": "https://service.example",
        "channelId": "msteams",
        "from": {"id": "person-1", "name": "Person"},
        "recipient": {"id": "bot-1", "name": "Darbot"},
        "conversation": {"id": "conversation-1", "tenantId": "tenant-1"},
        "text": "hello",
    }


@pytest.mark.parametrize("caller_claim", ["sender-controlled", {"unverified": ["sender-controlled", None]}])
def test_envelope_retains_original_json_and_fresh_projections_discard_caller_claims(
    incoming: dict[str, JsonValue],
    caller_claim: JsonValue,
) -> None:
    """DARPy retains complete untrusted ingress while isolating mutable typed projections."""
    conversation = incoming["conversation"]
    assert isinstance(conversation, dict)
    conversation["future-conversation-field"] = {"nested": None}
    incoming.update(
        {
            "callerId": caller_claim,
            "caller_id": "also-sender-controlled",
            "channelData": {"extension": [None, {"nested": True}]},
            "entities": [{"type": "future-entity", "x-foo": {"value": None}, "HTTPHeader": ["opaque"]}],
            "attachments": [
                {
                    "contentType": "application/json",
                    "content": {"unknown": [None, 2, "é"]},
                    "future-attachment-field": {"nested": None},
                }
            ],
            "future": {"null": None, "deep": [{"unrecognized": 42}]},
        }
    )
    wire_json = json.dumps(incoming, ensure_ascii=False, indent=2)
    envelope = ActivityEnvelope(wire_json)
    assert envelope.wire_json is wire_json
    assert envelope.to_dict() == incoming
    projection = envelope.activity
    assert projection.caller_id is None
    assert projection.model_dump(mode="json", by_alias=True, exclude_unset=True) == snapshot(
        {
            "type": "message",
            "channelId": "msteams",
            "id": "inbound-1",
            "serviceUrl": "https://service.example",
            "from": {"id": "person-1", "name": "Person"},
            "conversation": {"id": "conversation-1", "tenantId": "tenant-1"},
            "recipient": {"id": "bot-1", "name": "Darbot"},
            "text": "hello",
            "attachments": [{"contentType": "application/json", "content": {"unknown": [None, 2, "é"]}}],
            "entities": [{"type": "future-entity", "xFoo": {"value": None}, "httpHeader": ["opaque"]}],
            "channelData": {"extension": [None, {"nested": True}]},
        }
    )
    projection.text = "changed projection"
    channel_data = projection.channel_data
    assert isinstance(channel_data, dict)
    channel_data.clear()
    exported = envelope.to_dict()
    future = exported["future"]
    assert isinstance(future, dict)
    future["deep"] = "changed nested exported object"
    copied = ActivityEnvelope.from_dict(incoming)
    incoming["text"] = "changed original input"
    assert envelope.to_dict() == json.loads(wire_json)
    assert envelope.activity.text == "hello"
    assert copied.to_dict() == envelope.to_dict()
    with pytest.raises(FrozenInstanceError):
        setattr(envelope, "wire_json", "{}")


@pytest.mark.anyio
@pytest.mark.parametrize("capture_raw", [False, True])
async def test_host_sends_routed_reply_through_hooks_and_preserves_host_identity(
    incoming: dict[str, JsonValue], capture_raw: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DARPy uses the real send pipeline; raw capture retains extensions beyond the official projection."""
    monkeypatch.setattr(activity_module, "datetime", FixedDatetime)
    incoming["callerId"] = "sender-controlled"
    incoming["future"] = {"null": None, "nested": [1, 2]}
    envelope = ActivityEnvelope.from_dict(incoming)
    received: list[Task] = []

    async def execute(task: Task) -> str:
        assert task.protocol == "activity"
        received.append(task)
        return "runtime reply"

    handler = ActivityHandler(Runtime(execute))
    adapter = RecordingAdapter()
    identity = ClaimsIdentity({"subject": "verified-host-principal"}, authentication_type="host")
    context = TurnContext(adapter, envelope.activity, identity)
    context.activity.caller_id = "host-supplied"
    hook_responses: list[ResourceResponse] = []

    async def send_hook(
        turn: TurnContext, activities: list[Activity], next_send: Callable[[], Awaitable[list[ResourceResponse]]]
    ) -> list[ResourceResponse]:
        assert turn is context
        assert len(activities) == 1
        activities[0].text = f"hook: {activities[0].text}"
        responses = await next_send()
        hook_responses.extend(responses)
        return responses

    context.on_send_activities(send_hook)
    assert not context.responded
    assert await handle_turn(context, handler, envelope=envelope if capture_raw else None)
    assert context.responded
    assert context.identity is identity
    assert context.activity.caller_id == "host-supplied"
    assert hook_responses == adapter.responses
    assert hook_responses[0] is adapter.responses[0]
    assert len(received) == 1
    task = received[0]
    assert (task.prompt, task.protocol, task.request_id, task.cwd) == snapshot(("hello", "activity", "inbound-1", None))
    assert task.payload_json is not None
    if capture_raw:
        assert task.payload_json is envelope.wire_json
        assert json.loads(task.payload_json) == incoming
    else:
        assert json.loads(task.payload_json) == context.activity.model_dump(
            mode="json", by_alias=True, exclude_unset=True
        )
    assert [
        activity.model_dump(mode="json", by_alias=True, exclude_unset=True) for activity in adapter.sent
    ] == snapshot(
        [
            {
                "type": "message",
                "channelId": "msteams",
                "id": None,
                "timestamp": "2026-01-01T00:00:00Z",
                "serviceUrl": "https://service.example",
                "from": {"id": "bot-1", "name": "Darbot"},
                "conversation": {"id": "conversation-1", "tenantId": "tenant-1"},
                "recipient": {"id": "person-1", "name": "Person"},
                "text": "hook: runtime reply",
                "inputHint": "acceptingInput",
                "attachments": [],
                "entities": [],
                "replyToId": "inbound-1",
            }
        ]
    )


@pytest.mark.anyio
@pytest.mark.parametrize("activity_type", ["typing", "invoke", "event", "conversationUpdate", "futureActivity"])
async def test_non_message_turns_remain_available_to_other_host_routes(activity_type: str) -> None:
    """DARPy declines non-message activities without calling the runtime or marking the turn answered."""

    async def execute(task: Task) -> str:
        raise NotImplementedError

    adapter = RecordingAdapter()
    context = TurnContext(adapter, Activity(type=activity_type))
    assert not await handle_turn(context, ActivityHandler(Runtime(execute)))
    assert not context.responded
    assert adapter.sent == []


@pytest.mark.anyio
async def test_invalid_payloads_and_mismatched_turns_never_reach_runtime(incoming: dict[str, JsonValue]) -> None:
    """DARPy rejects malformed ingress and prevents a captured envelope from being attached to another turn."""
    for wire in ("[]", "null", "17"):
        with pytest.raises(ValueError) as error:
            ActivityEnvelope(wire)
        assert str(error.value) == snapshot("An Activity requires a JSON object")
    for wire in ('{"type": "message", "extra": NaN}', '{"type": "message", "extra": Infinity}'):
        with pytest.raises(ValueError):
            ActivityEnvelope(wire)
    with pytest.raises(json.JSONDecodeError):
        ActivityEnvelope("{")
    with pytest.raises(ValidationError) as invalid_type:
        ActivityEnvelope('{"type": 17}')
    assert invalid_type.value.errors()[0]["type"] == "string_type"

    async def execute(task: Task) -> str:
        raise NotImplementedError

    handler = ActivityHandler(Runtime(execute))
    with pytest.raises(ValueError) as missing_conversation:
        await handler.handle(ActivityEnvelope.from_dict({"type": "message"}))
    assert str(missing_conversation.value) == snapshot("A message requires a conversation identifier")
    with pytest.raises(ValidationError) as missing_identifier:
        ActivityEnvelope.from_dict({"type": "message", "conversation": {}})
    assert missing_identifier.value.errors()[0]["type"] == "missing"
    envelope = ActivityEnvelope.from_dict(incoming)
    adapter = RecordingAdapter()
    context = TurnContext(adapter, envelope.activity)
    context.activity.text = "a different request"
    with pytest.raises(ValueError) as mismatch:
        await handle_turn(context, handler, envelope=envelope)
    assert str(mismatch.value) == snapshot("The ingress envelope does not match the authenticated turn")
    assert not context.responded
    assert adapter.sent == []


@pytest.mark.anyio
async def test_sessions_are_stable_within_one_route_and_distinct_across_each_scope(
    incoming: dict[str, JsonValue],
) -> None:
    """DARPy correlation separates service, channel, tenant, and conversation without deriving authorization."""
    received: list[Task] = []

    async def execute(task: Task) -> str:
        assert task.protocol == "activity"
        received.append(task)
        return task.session_id

    handler = ActivityHandler(Runtime(execute))
    base = ActivityEnvelope.from_dict(incoming)
    first = await handler.handle(base)
    assert first is not None
    incoming["text"] = "another message"
    second = await handler.handle(ActivityEnvelope.from_dict(incoming))
    assert second is not None and first.text == second.text
    variants: list[dict[str, JsonValue]] = [
        {"serviceUrl": "https://other-service.example"},
        {"channelId": "other-channel"},
        {"conversation": {"id": "conversation-1", "tenantId": "other-tenant"}},
        {"conversation": {"id": "other-conversation", "tenantId": "tenant-1"}},
        {"channelId": None},
        {"channelId": "None"},
    ]
    replies: list[str] = []
    for variant in variants:
        reply = await handler.handle(ActivityEnvelope.from_dict(base.to_dict() | variant))
        assert reply is not None
        replies.append(reply.text)
    assert len({first.text, *replies}) == len(variants) + 1
    assert [task.session_id for task in received] == [first.text, first.text, *replies]
