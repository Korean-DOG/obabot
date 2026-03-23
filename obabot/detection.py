"""Platform detection for incoming webhook requests."""

import ipaddress
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Telegram official IP ranges
# Source: https://core.telegram.org/bots/webhooks
TELEGRAM_IP_RANGES = [
    "149.154.160.0/20",
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.12.0/22",
    "91.108.16.0/22",
    "91.108.56.0/22",
]

# Max IP ranges
# TODO: Add official Max IP ranges when available
MAX_IP_RANGES: list[str] = []

# Pre-compute network objects for faster matching
_telegram_networks = [ipaddress.ip_network(r) for r in TELEGRAM_IP_RANGES]
_max_networks = [ipaddress.ip_network(r) for r in MAX_IP_RANGES]


def extract_source_ip(event: Optional[dict]) -> Optional[str]:
    """
    Extract source IP from webhook event (Yandex Cloud Functions, AWS Lambda, etc.).
    
    Checks in order:
    1. requestContext.identity.sourceIp (YCF / AWS API Gateway)
    2. X-Real-Ip header (Nginx proxy)
    3. X-Forwarded-For header - first IP (Load balancer)
    
    Args:
        event: Webhook event dict containing request metadata
        
    Returns:
        Source IP address string or None
        
    Example:
        # AWS Lambda / Yandex Cloud Functions
        ip = extract_source_ip(event)
        if ip:
            print(f"Request from: {ip}")
    """
    if not event:
        return None
    
    headers = event.get("headers", {})
    forwarded_for = headers.get("X-Forwarded-For", "") if headers else ""
    
    return (
        event.get("requestContext", {}).get("identity", {}).get("sourceIp")
        or (headers.get("X-Real-Ip") if headers else None)
        or (forwarded_for.split(",")[0].strip() if forwarded_for else None)
        or None
    )


def _is_ip_in_ranges(ip_str: str, networks: list[ipaddress.IPv4Network]) -> bool:
    """Check if IP address is in any of the given network ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in network for network in networks)
    except ValueError:
        logger.warning(f"Invalid IP address: {ip_str}")
        return False


def _detect_platform_by_ip(ip: str) -> Optional[str]:
    """
    Detect platform by source IP address.
    
    Args:
        ip: Source IP address
        
    Returns:
        "telegram", "max", or None if not recognized
    """
    if _is_ip_in_ranges(ip, _telegram_networks):
        return "telegram"
    
    if _max_networks and _is_ip_in_ranges(ip, _max_networks):
        return "max"
    
    return None


def _detect_platform_by_payload(body: dict) -> str:
    """
    Detect platform by analyzing payload structure.
    
    Telegram: "update_id" at root (unique to Telegram).
    Max: unique message id "mid" in message.body (Max/umaxbot only; Telegram has no message.body),
         or "update_type" at root (e.g. message_created, message_callback).
    Yandex Messenger: "updates" array at root with items containing "from.login"
         (Yandex users have login like user@org.ru).
    
    Args:
        body: Parsed webhook body
        
    Returns:
        "telegram", "max", "yandex", or "unknown"
    """
    if not isinstance(body, dict):
        return "unknown"
    
    # Check for Telegram format: has "update_id" at root
    if "update_id" in body:
        return "telegram"
    
    # Check for Yandex Messenger format: webhook sends {"updates": [...]}
    # Each update has "from.login" (email-like) and "chat.type" = "private"|"group"
    updates = body.get("updates")
    if isinstance(updates, list) and updates:
        sample = updates[0]
        if isinstance(sample, dict):
            from_data = sample.get("from", {})
            if isinstance(from_data, dict) and "login" in from_data:
                return "yandex"
    # Single Yandex update (non-wrapped)
    from_data = body.get("from", {})
    if isinstance(from_data, dict) and "login" in from_data and "update_id" not in body:
        if "message_id" in body and "timestamp" in body:
            return "yandex"
    
    # Check for Max format (Max/umaxbot webhook payload)
    # Primary indicator: unique message id "mid" in message.body (Max-specific; Telegram has no message.body)
    message = body.get("message", {})
    if isinstance(message, dict):
        msg_body = message.get("body", {})
        if isinstance(msg_body, dict) and "mid" in msg_body:
            return "max"
    # Secondary: "update_type" at root (e.g. message_created, message_callback)
    if "update_type" in body:
        return "max"

    return "unknown"


def detect_platform(body: dict, event: Optional[dict] = None) -> str:
    """
    Detect which platform sent the webhook request.
    
    Detection strategy:
    1. First, try to detect by source IP address (most reliable)
    2. If IP not recognized, fallback to payload structure analysis
    
    Args:
        body: Parsed webhook body (JSON payload)
        event: Optional AWS Lambda event dict containing request metadata
               (headers, requestContext, etc.)
    
    Returns:
        Platform identifier: "telegram", "max", "yandex", or "unknown"
        
    Example:
        # AWS Lambda handler
        def handler(event, context):
            body = json.loads(event["body"])
            platform = detect_platform(body, event)
            
            if platform == "telegram":
                # Handle Telegram update
                ...
            elif platform == "max":
                # Handle Max update
                ...
    """
    # Try IP-based detection first
    source_ip = extract_source_ip(event)
    if source_ip:
        platform = _detect_platform_by_ip(source_ip)
        if platform:
            logger.debug(f"Detected platform '{platform}' by IP: {source_ip}")
            return platform
    
    # Fallback to payload-based detection
    platform = _detect_platform_by_payload(body)
    logger.debug(f"Detected platform '{platform}' by payload structure")
    return platform
