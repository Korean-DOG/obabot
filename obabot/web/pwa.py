"""create_mobile — add PWA capabilities to a FastAPI application."""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PWA asset generators
# ---------------------------------------------------------------------------

_DEFAULT_ICON_SIZES = ["192x192", "512x512"]


def _build_manifest(
    name: str,
    short_name: str,
    icons_path: str,
    theme_color: str,
    start_url: str,
    icon_sizes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    sizes = icon_sizes or _DEFAULT_ICON_SIZES
    icons_prefix = icons_path.rstrip("/")

    icons: List[Dict[str, str]] = []
    for size in sizes:
        px = size.split("x")[0]
        icons.append({
            "src": f"{icons_prefix}/icon-{px}.png",
            "sizes": size,
            "type": "image/png",
        })

    return {
        "name": name,
        "short_name": short_name,
        "start_url": start_url,
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": theme_color,
        "icons": icons,
    }


def _build_service_worker(static_prefix: str = "/static") -> str:
    return f"""\
const CACHE_NAME = 'obabot-pwa-v1';
const STATIC_ASSETS = [
    '/',
    '{static_prefix}/manifest.json',
];

self.addEventListener('install', event => {{
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
}});

self.addEventListener('fetch', event => {{
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
}});

self.addEventListener('activate', event => {{
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            )
        )
    );
}});
"""


def _build_index_html(
    name: str,
    theme_color: str,
    manifest_url: str = "/static/manifest.json",
    sw_url: str = "/service-worker.js",
) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="theme-color" content="{theme_color}">
    <link rel="manifest" href="{manifest_url}">
    <title>{name}</title>
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
             display:flex;flex-direction:column;height:100vh;background:#f5f5f5}}
        #chat{{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:8px}}
        .msg{{max-width:80%;padding:10px 14px;border-radius:16px;font-size:15px;line-height:1.4;word-wrap:break-word}}
        .msg.user{{align-self:flex-end;background:{theme_color};color:#fff;border-bottom-right-radius:4px}}
        .msg.bot{{align-self:flex-start;background:#fff;border:1px solid #e0e0e0;border-bottom-left-radius:4px}}
        .buttons{{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}}
        .buttons button{{padding:6px 12px;border:1px solid {theme_color};border-radius:12px;
                         background:#fff;color:{theme_color};cursor:pointer;font-size:13px}}
        .buttons button:hover{{background:{theme_color};color:#fff}}
        #input-area{{display:flex;padding:8px;background:#fff;border-top:1px solid #e0e0e0}}
        #input-area input{{flex:1;padding:10px;border:1px solid #ddd;border-radius:20px;font-size:15px;outline:none}}
        #input-area input:focus{{border-color:{theme_color}}}
        #input-area button{{margin-left:8px;padding:10px 18px;background:{theme_color};color:#fff;
                            border:none;border-radius:20px;font-size:15px;cursor:pointer}}
    </style>
</head>
<body>
    <div id="chat"></div>
    <div id="input-area">
        <input id="msg" placeholder="Сообщение…" autocomplete="off">
        <button onclick="send()">→</button>
    </div>
    <script>
        const API = '/api';
        const userId = Math.floor(Math.random()*1e9);
        const chat = document.getElementById('chat');
        const inp = document.getElementById('msg');

        inp.addEventListener('keydown', e => {{ if(e.key==='Enter') send(); }});

        function addMsg(text, cls, buttons) {{
            const d = document.createElement('div');
            d.className = 'msg ' + cls;
            d.textContent = text;
            if (buttons) {{
                const bw = document.createElement('div');
                bw.className = 'buttons';
                buttons.forEach(b => {{
                    const btn = document.createElement('button');
                    btn.textContent = b.text;
                    if (b.callback_data) btn.onclick = () => sendCb(b.callback_data, text);
                    if (b.url) btn.onclick = () => window.open(b.url);
                    bw.appendChild(btn);
                }});
                d.appendChild(bw);
            }}
            chat.appendChild(d);
            chat.scrollTop = chat.scrollHeight;
        }}

        async function send() {{
            const text = inp.value.trim();
            if (!text) return;
            inp.value = '';
            addMsg(text, 'user');
            const res = await fetch(API+'/webhook', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{user_id: userId, text}})
            }});
            const data = await res.json();
            (data.responses||[]).forEach(r => {{
                if (r.text) {{
                    const kb = r.reply_markup;
                    let btns = null;
                    if (kb && kb.inline_keyboard) btns = kb.inline_keyboard.flat();
                    addMsg(r.text, 'bot', btns);
                }}
            }});
        }}

        async function sendCb(cbData, msgText) {{
            const res = await fetch(API+'/callback', {{
                method:'POST', headers:{{'Content-Type':'application/json'}},
                body: JSON.stringify({{user_id: userId, callback_data: cbData, message_text: msgText}})
            }});
            const data = await res.json();
            (data.responses||[]).forEach(r => {{
                if (r.text) {{
                    const kb = r.reply_markup;
                    let btns = null;
                    if (kb && kb.inline_keyboard) btns = kb.inline_keyboard.flat();
                    addMsg(r.text, 'bot', btns);
                }}
            }});
        }}

        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('{sw_url}');
        }}
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_mobile(
    web_app: Any,
    name: str,
    short_name: str,
    icons: str,
    theme_color: str,
    offline_enabled: bool = True,
    start_url: str = "/",
    static_prefix: str = "/static",
) -> Any:
    """Turn a FastAPI app into an installable PWA.

    Adds ``manifest.json``, ``service-worker.js``, and a minimal
    ``index.html`` chat interface so a browser can install the app
    on the home screen.

    Args:
        web_app: ``FastAPI`` instance (usually the return value of
            :func:`create_web`).
        name: Full application name (shown in the install prompt).
        short_name: Short name (shown below the icon on home screen).
        icons: Path prefix to icon directory (must contain
            ``icon-192.png`` and ``icon-512.png``).
        theme_color: Theme colour in ``#RRGGBB`` format.
        offline_enabled: Generate a service worker for basic offline
            caching of static assets.
        start_url: The URL opened when the PWA is launched.
        static_prefix: URL prefix under which manifest and icons are
            served.

    Returns:
        The same ``FastAPI`` instance with PWA routes added.
    """
    try:
        from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
    except ImportError:
        raise ImportError(
            "fastapi is required for create_mobile. "
            "Install with: pip install obabot[web]"
        )

    manifest = _build_manifest(
        name=name,
        short_name=short_name,
        icons_path=icons,
        theme_color=theme_color,
        start_url=start_url,
    )

    manifest_url = f"{static_prefix}/manifest.json"
    sw_url = "/service-worker.js"

    index_html = _build_index_html(
        name=name,
        theme_color=theme_color,
        manifest_url=manifest_url,
        sw_url=sw_url,
    )
    sw_js = _build_service_worker(static_prefix) if offline_enabled else ""

    # -- routes -------------------------------------------------------------

    @web_app.get(f"{static_prefix}/manifest.json")
    async def serve_manifest() -> JSONResponse:
        return JSONResponse(content=manifest)

    if offline_enabled:
        @web_app.get("/service-worker.js")
        async def serve_sw() -> PlainTextResponse:
            return PlainTextResponse(sw_js, media_type="application/javascript")

    @web_app.get(start_url)
    async def serve_index() -> HTMLResponse:
        return HTMLResponse(content=index_html)

    logger.info(
        "[web PWA] PWA enabled: name=%r start=%s offline=%s",
        name, start_url, offline_enabled,
    )

    return web_app
