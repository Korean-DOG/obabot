"""Tests for platform detection."""

import pytest
from obabot.detection import (
    detect_platform,
    extract_source_ip,
    _detect_platform_by_ip,
    _detect_platform_by_payload,
    TELEGRAM_IP_RANGES,
)


class TestIPExtraction:
    """Test IP address extraction from events."""
    
    def test_extract_from_aws_api_gateway(self):
        """Test IP extraction from requestContext.identity.sourceIp (YCF/AWS)."""
        event = {
            "requestContext": {
                "identity": {
                    "sourceIp": "149.154.167.220"
                }
            }
        }
        assert extract_source_ip(event) == "149.154.167.220"
    
    def test_extract_from_x_real_ip(self):
        """Test IP extraction from X-Real-Ip header (Nginx proxy)."""
        event = {
            "headers": {
                "X-Real-Ip": "91.108.8.100"
            }
        }
        assert extract_source_ip(event) == "91.108.8.100"
    
    def test_extract_from_x_forwarded_for(self):
        """Test IP extraction from X-Forwarded-For (first IP from load balancer)."""
        event = {
            "headers": {
                "X-Forwarded-For": "149.154.161.1, 10.0.0.1, 192.168.1.1"
            }
        }
        assert extract_source_ip(event) == "149.154.161.1"
    
    def test_extract_none_when_event_empty(self):
        """Test that None is returned when event is None or empty."""
        assert extract_source_ip(None) is None
        assert extract_source_ip({}) is None
        assert extract_source_ip({"headers": {}}) is None
    
    def test_extract_source_ip_exported(self):
        """Test that extract_source_ip is exported from obabot package."""
        from obabot import extract_source_ip as exported_func
        assert exported_func is not None
        assert callable(exported_func)


class TestIPBasedDetection:
    """Test IP-based platform detection."""
    
    def test_telegram_ip_in_149_154_range(self):
        """Test Telegram detection for 149.154.160.0/20 range."""
        # 149.154.160.0 - 149.154.175.255
        assert _detect_platform_by_ip("149.154.160.1") == "telegram"
        assert _detect_platform_by_ip("149.154.167.220") == "telegram"
        assert _detect_platform_by_ip("149.154.175.255") == "telegram"
    
    def test_telegram_ip_in_91_108_ranges(self):
        """Test Telegram detection for 91.108.x.0/22 ranges."""
        # 91.108.4.0/22
        assert _detect_platform_by_ip("91.108.4.1") == "telegram"
        assert _detect_platform_by_ip("91.108.7.255") == "telegram"
        
        # 91.108.8.0/22
        assert _detect_platform_by_ip("91.108.8.1") == "telegram"
        
        # 91.108.12.0/22
        assert _detect_platform_by_ip("91.108.12.1") == "telegram"
        
        # 91.108.16.0/22
        assert _detect_platform_by_ip("91.108.16.1") == "telegram"
        
        # 91.108.56.0/22
        assert _detect_platform_by_ip("91.108.56.1") == "telegram"
    
    def test_non_telegram_ip(self):
        """Test that non-Telegram IPs return None."""
        assert _detect_platform_by_ip("8.8.8.8") is None
        assert _detect_platform_by_ip("192.168.1.1") is None
        assert _detect_platform_by_ip("10.0.0.1") is None
    
    def test_invalid_ip(self):
        """Test handling of invalid IP addresses."""
        assert _detect_platform_by_ip("not-an-ip") is None
        assert _detect_platform_by_ip("") is None


class TestPayloadBasedDetection:
    """Test payload-based platform detection."""
    
    def test_telegram_by_update_id(self):
        """Test Telegram detection by update_id field."""
        body = {
            "update_id": 907259674,
            "message": {
                "message_id": 123,
                "chat": {"id": 456, "type": "private"},
                "text": "/start"
            }
        }
        assert _detect_platform_by_payload(body) == "telegram"
    
    def test_telegram_callback_query(self):
        """Test Telegram detection for callback_query updates."""
        body = {
            "update_id": 907259675,
            "callback_query": {
                "id": "123",
                "data": "button_click"
            }
        }
        assert _detect_platform_by_payload(body) == "telegram"
    
    def test_max_by_mid(self):
        """Test Max detection by mid field in message.body."""
        body = {
            "timestamp": 1772044796144,
            "message": {
                "recipient": {"chat_id": 137522054, "chat_type": "dialog"},
                "body": {
                    "mid": "mid.0000000008326b86019c9619c0f06a52",
                    "seq": 116132727760120402,
                    "text": "/start"
                },
                "sender": {"user_id": 32504585, "first_name": "Test"}
            },
            "user_locale": "ru",
            "update_type": "message_created"
        }
        assert _detect_platform_by_payload(body) == "max"
    
    def test_max_by_update_type(self):
        """Test Max detection by update_type field."""
        body = {
            "update_type": "message_callback",
            "callback": {"payload": "test"}
        }
        assert _detect_platform_by_payload(body) == "max"
    
    def test_unknown_payload(self):
        """Test unknown platform for unrecognized payloads."""
        assert _detect_platform_by_payload({}) == "unknown"
        assert _detect_platform_by_payload({"random": "data"}) == "unknown"
        assert _detect_platform_by_payload(None) == "unknown"
        assert _detect_platform_by_payload("not a dict") == "unknown"


class TestDetectPlatform:
    """Test the main detect_platform function."""
    
    def test_detect_telegram_by_ip(self):
        """Test Telegram detection by IP address."""
        body = {"some": "data"}  # No identifying fields
        event = {
            "requestContext": {
                "identity": {"sourceIp": "149.154.167.220"}
            }
        }
        assert detect_platform(body, event) == "telegram"
    
    def test_detect_telegram_by_payload_fallback(self):
        """Test Telegram detection by payload when IP not recognized."""
        body = {
            "update_id": 123456,
            "message": {"text": "hello"}
        }
        event = {
            "requestContext": {
                "identity": {"sourceIp": "8.8.8.8"}  # Not a Telegram IP
            }
        }
        assert detect_platform(body, event) == "telegram"
    
    def test_detect_telegram_by_payload_no_event(self):
        """Test Telegram detection by payload when no event provided."""
        body = {
            "update_id": 123456,
            "message": {"text": "hello"}
        }
        assert detect_platform(body, None) == "telegram"
        assert detect_platform(body) == "telegram"
    
    def test_detect_max_by_payload(self):
        """Test Max detection by payload structure."""
        body = {
            "timestamp": 1772044796144,
            "message": {
                "body": {
                    "mid": "mid.0000000008326b86019c9619c0f06a52",
                    "text": "/start"
                }
            },
            "update_type": "message_created"
        }
        assert detect_platform(body) == "max"
    
    def test_detect_max_by_update_type_only(self):
        """Test Max detection by update_type when mid not present."""
        body = {
            "update_type": "bot_started",
            "user": {"user_id": 123}
        }
        assert detect_platform(body) == "max"
    
    def test_detect_unknown(self):
        """Test unknown platform detection."""
        body = {"random": "data"}
        assert detect_platform(body) == "unknown"
    
    def test_ip_takes_priority(self):
        """Test that IP detection takes priority over payload."""
        # Even if payload looks like Max, Telegram IP should win
        body = {
            "update_type": "message_created",
            "message": {"body": {"mid": "some-mid"}}
        }
        event = {
            "requestContext": {
                "identity": {"sourceIp": "149.154.167.220"}
            }
        }
        assert detect_platform(body, event) == "telegram"


class TestYandexPayloadDetection:
    """Test Yandex Messenger payload-based detection."""

    def test_yandex_by_updates_array_with_login(self):
        """Yandex webhooks send {"updates": [...]} with from.login."""
        body = {
            "updates": [
                {
                    "from": {"login": "user@yandex.ru", "display_name": "Test"},
                    "text": "hello",
                    "chat": {"id": "chat123", "type": "private"},
                    "message_id": 1,
                    "timestamp": 1700000000,
                }
            ]
        }
        assert _detect_platform_by_payload(body) == "yandex"

    def test_yandex_single_update_with_login(self):
        """Single (non-wrapped) Yandex update with from.login."""
        body = {
            "from": {"login": "user@yandex.ru", "display_name": "Test"},
            "text": "hello",
            "message_id": 42,
            "timestamp": 1700000000,
        }
        assert _detect_platform_by_payload(body) == "yandex"

    def test_yandex_callback_in_updates(self):
        """Yandex callback update inside updates array."""
        body = {
            "updates": [
                {
                    "from": {"login": "user@org.ru", "display_name": "User"},
                    "callback_data": "btn_ok",
                    "message_id": 5,
                    "timestamp": 1700000000,
                }
            ]
        }
        assert _detect_platform_by_payload(body) == "yandex"

    def test_yandex_not_confused_with_telegram(self):
        """Telegram has update_id; Yandex does not."""
        body = {
            "update_id": 12345,
            "from": {"login": "user@yandex.ru"},
            "message_id": 1,
            "timestamp": 1700000000,
        }
        assert _detect_platform_by_payload(body) == "telegram"

    def test_detect_platform_yandex_full(self):
        """detect_platform() should identify Yandex webhook payloads."""
        body = {
            "updates": [
                {
                    "from": {"login": "bot@org.ru"},
                    "text": "/start",
                    "chat": {"id": "c1", "type": "private"},
                    "message_id": 1,
                    "timestamp": 1700000000,
                }
            ]
        }
        assert detect_platform(body) == "yandex"


class TestTelegramIPRanges:
    """Verify Telegram IP ranges are configured correctly."""
    
    def test_ip_ranges_are_valid(self):
        """Test that all configured IP ranges are valid."""
        import ipaddress
        for ip_range in TELEGRAM_IP_RANGES:
            # Should not raise
            network = ipaddress.ip_network(ip_range)
            assert network is not None
    
    def test_expected_ranges_present(self):
        """Test that expected Telegram ranges are present."""
        assert "149.154.160.0/20" in TELEGRAM_IP_RANGES
        assert "91.108.4.0/22" in TELEGRAM_IP_RANGES
        assert "91.108.8.0/22" in TELEGRAM_IP_RANGES
        assert "91.108.12.0/22" in TELEGRAM_IP_RANGES
        assert "91.108.16.0/22" in TELEGRAM_IP_RANGES
        assert "91.108.56.0/22" in TELEGRAM_IP_RANGES
