"""create_web — build a FastAPI app wired to an existing obabot dispatcher."""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def create_web(
    dp: Any,
    base_path: str = "/api",
    auth_config: Optional[Dict[str, Any]] = None,
    bot_id: int = 0,
) -> Any:
    """Create a FastAPI application backed by an obabot dispatcher.

    Args:
        dp: ``ProxyDispatcher`` (or aiogram ``Dispatcher``) that already
            has all handlers registered via ``router.message()`` /
            ``router.callback_query()`` etc.
        base_path: URL prefix for every API endpoint (default ``/api``).
        auth_config: If provided, enables JWT authentication.  Must contain
            ``"secret_key"``; may contain ``"algorithm"`` (default HS256).
        bot_id: ``bot_id`` used in FSM storage keys so web and messenger
            platforms can share FSM state.  Set this to your Telegram
            bot's numeric id for cross-platform state sync.

    Returns:
        A ``FastAPI`` application instance ready to be served by uvicorn.
    """
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
    except ImportError:
        raise ImportError(
            "fastapi and pydantic are required for the web layer. "
            "Install with: pip install obabot[web]"
        )

    from obabot.web.emulators import WebBot, WebMessage, WebCallbackQuery
    from obabot.web.dispatch import (
        dispatch_message,
        dispatch_callback,
        WebFSMContext,
    )

    # -- pydantic models for request bodies ---------------------------------

    class WebhookRequest(BaseModel):
        user_id: int
        text: str = ""
        chat_id: Optional[int] = None

    class CallbackRequest(BaseModel):
        user_id: int
        callback_data: str
        message_id: Optional[int] = None
        chat_id: Optional[int] = None
        message_text: str = ""

    # -- FastAPI app --------------------------------------------------------

    app = FastAPI(title="obabot web API")

    # -- optional JWT auth --------------------------------------------------

    if auth_config and auth_config.get("secret_key"):
        from obabot.web.auth import create_auth_middleware

        auth_mw = create_auth_middleware(auth_config["secret_key"])
        app.middleware("http")(auth_mw)

    # -- endpoints ----------------------------------------------------------

    @app.post(f"{base_path}/webhook")
    async def webhook(req: WebhookRequest) -> Dict[str, Any]:
        """Accept a text message and return bot responses."""
        web_bot = WebBot()
        msg = WebMessage(
            bot=web_bot,
            user_id=req.user_id,
            text=req.text,
            chat_id=req.chat_id,
        )
        await dispatch_message(dp, web_bot, msg, bot_id=bot_id)
        return {"responses": web_bot.outgoing}

    @app.post(f"{base_path}/callback")
    async def callback(req: CallbackRequest) -> Dict[str, Any]:
        """Accept a callback-button press and return bot responses."""
        web_bot = WebBot()
        cb = WebCallbackQuery(
            bot=web_bot,
            user_id=req.user_id,
            callback_data=req.callback_data,
            chat_id=req.chat_id,
            message_id=req.message_id,
            message_text=req.message_text,
        )
        await dispatch_callback(dp, web_bot, cb, bot_id=bot_id)
        return {"responses": web_bot.outgoing}

    @app.get(f"{base_path}/state/{{user_id}}")
    async def get_state(user_id: int, chat_id: Optional[int] = None) -> Dict[str, Any]:
        """Return current FSM state and data for a user."""
        fsm_storage = (
            getattr(dp, "_fsm_storage", None)
            or getattr(dp, "fsm_storage", None)
        )
        if not fsm_storage:
            return {"state": None, "data": {}}

        cid = chat_id or user_id
        ctx = WebFSMContext(fsm_storage, user_id, cid, bot_id)
        return {
            "state": await ctx.get_state(),
            "data": await ctx.get_data(),
        }

    @app.post(f"{base_path}/reset/{{user_id}}")
    async def reset_state(user_id: int, chat_id: Optional[int] = None) -> Dict[str, Any]:
        """Reset FSM state and data for a user."""
        fsm_storage = (
            getattr(dp, "_fsm_storage", None)
            or getattr(dp, "fsm_storage", None)
        )
        if not fsm_storage:
            return {"ok": False, "detail": "no FSM storage configured"}

        cid = chat_id or user_id
        ctx = WebFSMContext(fsm_storage, user_id, cid, bot_id)
        await ctx.clear()
        return {"ok": True}

    # -- optional auth token endpoint ---------------------------------------

    if auth_config and auth_config.get("secret_key"):
        from obabot.web.auth import generate_token

        @app.post(f"{base_path}/auth")
        async def auth(user_id: int) -> Dict[str, str]:
            """Generate a JWT token for the given user_id."""
            token = generate_token(user_id, auth_config["secret_key"])
            return {"token": token}

    return app
