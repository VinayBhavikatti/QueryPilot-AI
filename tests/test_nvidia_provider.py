import unittest
from unittest.mock import patch

from openai import APIConnectionError, APIStatusError

from app.config import Settings, get_settings
from app.llm import _client


class NvidiaProviderTests(unittest.TestCase):
    def test_default_provider_configuration(self):
        settings = Settings(_env_file=None, _env_prefix="__TEST__")
        self.assertEqual(settings.nvidia_base_url, "https://integrate.api.nvidia.com/v1")
        self.assertEqual(settings.nvidia_model, "nvidia/nemotron-3.5-lightning-30b-a3b")

    def test_client_requires_nvidia_key_without_fallback(self):
        settings = Settings(_env_file=None, nvidia_api_key="")
        with patch("app.llm.get_settings", return_value=settings):
            with self.assertRaisesRegex(RuntimeError, "NVIDIA_API_KEY"):
                _client()

    def test_live_provider_connection(self):
        """Send one short prompt when a real NVIDIA key is configured."""
        settings = get_settings()
        api_key = settings.nvidia_api_key.get_secret_value()
        if not api_key or api_key == "replace-me":
            self.skipTest("NVIDIA_API_KEY is missing or still a placeholder")

        try:
            response = _client().chat.completions.create(
                model=settings.nvidia_model,
                messages=[{"role": "user", "content": "Reply with OK."}],
                max_tokens=8,
                temperature=0,
            )
        except APIConnectionError:
            raise AssertionError("NVIDIA provider connection failed: network or endpoint error.") from None
        except APIStatusError as error:
            status = error.status_code
            if status == 401:
                reason = "authentication failed; check NVIDIA_API_KEY"
            elif status == 403:
                reason = "access denied; check account and model permissions"
            elif status == 404:
                reason = "model endpoint or model ID was not found"
            elif status == 429:
                reason = "quota or rate limit was reached"
            else:
                reason = f"provider returned HTTP {status}"
            raise AssertionError(f"NVIDIA provider request failed: {reason}.") from None
        except Exception as error:
            raise AssertionError(
                f"NVIDIA connectivity test failed ({type(error).__name__})."
            ) from None

        self.assertTrue(response.choices, "NVIDIA returned no completion choices")


if __name__ == "__main__":
    unittest.main()
