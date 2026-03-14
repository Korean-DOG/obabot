"""Proxy classes that multiplex operations across platforms."""

from obabot.proxy.bot import ProxyBot, ProxyFile, DownloadableFile
from obabot.proxy.dispatcher import ProxyDispatcher
from obabot.proxy.router import ProxyRouter

__all__ = ["ProxyBot", "ProxyFile", "DownloadableFile", "ProxyDispatcher", "ProxyRouter"]

