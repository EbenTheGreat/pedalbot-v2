
import os
import unittest
from unittest.mock import patch
from backend.config.config import Settings

class TestRedisConfig(unittest.TestCase):
    
    def test_redis_url_priority_env_var(self):
        """Test that os.environ['REDIS_URL'] has highest priority."""
        with patch.dict(os.environ, {"REDIS_URL": "redis://env-var-url:6379/2"}):
            settings = Settings()
            print(f"DEBUG: os.environ['REDIS_URL'] in test: {os.environ.get('REDIS_URL')}")
            print(f"DEBUG: settings.redis_url in test: {settings.redis_url}")
            self.assertEqual(settings.redis_url, "redis://env-var-url:6379/2")
            self.assertEqual(settings.get_celery_broker_url(), "redis://env-var-url:6379/2")

    def test_redis_uri_priority_env_var(self):
        """Test that os.environ['REDIS_URI'] is used if REDIS_URL is missing."""
        with patch.dict(os.environ, {"REDIS_URI": "redis://env-uri-url:6379/3"}):
            # Ensure REDIS_URL is not in env
            if "REDIS_URL" in os.environ:
                del os.environ["REDIS_URL"]
            settings = Settings()
            self.assertEqual(settings.redis_url, "redis://env-uri-url:6379/3")

    def test_settings_field_priority(self):
        """Test that settings fields are used if env vars are missing."""
        # Clear env vars
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(REDIS_URL_ENV="redis://settings-url:6379/4")
            self.assertEqual(settings.redis_url, "redis://settings-url:6379/4")

    def test_default_fallback(self):
        """Test fallback to localhost."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings(REDIS_URL_ENV=None, REDIS_URI=None)
            self.assertEqual(settings.redis_url, "redis://localhost:6379/0")

    def test_celery_specific_override(self):
        """Test that Celery URLs can still be specifically overridden via environment."""
        with patch.dict(os.environ, {
            "REDIS_URL": "redis://global:6379/0",
            "CELERY_RESULT_BACKEND": "redis://custom-backend:6379/9"
        }):
            settings = Settings()
            # Broker should follow REDIS_URL
            self.assertEqual(settings.get_celery_broker_url(), "redis://global:6379/0")
            # Backend should follow CELERY_RESULT_BACKEND
            self.assertEqual(settings.get_celery_backend(), "redis://custom-backend:6379/9")

if __name__ == "__main__":
    unittest.main()
