"""Helpers for MAX Bot API calls that need obabot-side workarounds."""

from typing import Any


async def delete_max_message(bot: Any, message_id: Any) -> Any:
    """Delete a MAX message using Authorization header when possible.

    `umaxbot 0.2.0` still sends `access_token` as a query param for
    `delete_message()`, but MAX Bot API now expects `Authorization` header.
    If the native bot exposes `_request()`, prefer it because it already sets
    the correct header. Fall back to the library method for older versions.
    """
    message_id_str = str(message_id)

    request = getattr(bot, "_request", None)
    if callable(request):
        return await request(
            "DELETE",
            "/messages",
            params={"message_id": message_id_str},
        )

    delete_message = getattr(bot, "delete_message", None)
    if callable(delete_message):
        return await delete_message(message_id=message_id_str)

    raise AttributeError("Max bot does not provide delete_message() or _request()")
