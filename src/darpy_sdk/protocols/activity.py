"""Lossless Activity records and message dispatch through the DARPy runtime."""

import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import uuid4

from microsoft_agents.activity import Activity, ActivityTypes
from pydantic import JsonValue

from darpy_sdk.runtime import Runtime, Task

__all__ = ["ActivityEnvelope", "ActivityHandler"]


@dataclass(frozen=True)
class ActivityEnvelope:
    """Retain original JSON, including fields omitted by the typed projection.

    Capture this at ingress, before the official Activity model drops unknown
    fields. The envelope is data, not evidence of an authenticated sender.
    """

    wire_json: str

    def __post_init__(self) -> None:
        payload = json.loads(self.wire_json)
        if not isinstance(payload, dict):
            raise ValueError("An Activity requires a JSON object")
        json.dumps(payload, allow_nan=False)
        _ = self.activity

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> ActivityEnvelope:
        """Validate and snapshot a wire object, preserving unknown nested fields."""
        return cls(json.dumps(payload, ensure_ascii=False, allow_nan=False))

    @property
    def activity(self) -> Activity:
        """Return a fresh typed projection, discarding untrusted wire callerId."""
        payload = self.to_dict()
        payload.pop("callerId", None)
        payload.pop("caller_id", None)
        return Activity.model_validate(payload)

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a fresh wire object suitable for lossless field forwarding."""
        return cast(dict[str, JsonValue], json.loads(self.wire_json))


class ActivityHandler:
    """Dispatch messages after host authentication; defer other activity types.

    The full ingress payload is available in ``Task.payload_json``. No invoke,
    OAuth, attachment download, or channel authentication behavior is implied.
    """

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime

    async def handle(self, envelope: ActivityEnvelope) -> Activity | None:
        """Execute a message and construct its officially routed reply."""
        activity = envelope.activity
        if activity.type != ActivityTypes.message:
            return None
        if not activity.conversation:
            raise ValueError("A message requires a conversation identifier")
        scope = [
            activity.service_url,
            activity.channel_id,
            activity.conversation.tenant_id,
            activity.conversation.id,
        ]
        session_id = hashlib.sha256(json.dumps(scope).encode("utf-8")).hexdigest()
        result = await self.runtime.run(
            Task(
                prompt=activity.text or "",
                session_id=session_id,
                protocol="activity",
                payload_json=envelope.wire_json,
                request_id=activity.id or uuid4().hex,
            )
        )
        return activity.create_reply(result.text)
