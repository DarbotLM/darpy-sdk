"""Attach a DARPy message handler to the Microsoft Agents turn pipeline."""

from microsoft_agents.hosting.core import TurnContext

from darpy_sdk.protocols.activity import ActivityEnvelope, ActivityHandler


async def handle_turn(
    context: TurnContext, handler: ActivityHandler, *, envelope: ActivityEnvelope | None = None
) -> bool:
    """Send message replies through the host adapter; return False for other types.

    The host owns authentication and middleware. Pass the raw ingress envelope
    to preserve unknown fields. Its typed projection must match this turn;
    otherwise the request is rejected before handler execution.
    """
    if envelope is None:
        envelope = ActivityEnvelope(context.activity.model_dump_json(by_alias=True, exclude_unset=True))
    elif envelope.activity.model_dump(exclude={"caller_id"}) != context.activity.model_dump(exclude={"caller_id"}):
        raise ValueError("The ingress envelope does not match the authenticated turn")
    reply = await handler.handle(envelope)
    if reply is None:
        return False
    await context.send_activity(reply)
    return True
