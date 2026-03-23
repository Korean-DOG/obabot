"""obabot.web — web API and PWA layer for obabot bots.

Usage::

    from obabot import create_bot
    from obabot.web import create_web, create_mobile

    bot, dp, router = create_bot(tg_token='...', max_token='...', yandex_token='...')
    # … register handlers on router …

    web_app = create_web(dp, base_path='/api')
    mobile_app = create_mobile(
        web_app, name='My Bot', short_name='Bot',
        icons='/static/icons/', theme_color='#000000',
    )
"""

from obabot.web.api import create_web
from obabot.web.pwa import create_mobile

__all__ = ["create_web", "create_mobile"]
