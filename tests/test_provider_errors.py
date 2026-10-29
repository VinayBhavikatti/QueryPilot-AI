import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from openai import APIConnectionError

from app.main import app


class ProviderErrorHandlingTests(unittest.TestCase):
    def test_connection_error_is_safe_and_diagnostic(self):
        request = httpx.Request("POST", "https://provider.invalid/v1/chat/completions")
        error = APIConnectionError(message="secret-token-must-not-leak", request=request)
        with (
            patch("app.main.get_schema", return_value="students(id int)"),
            patch("app.main.generate_sql", side_effect=error),
            TestClient(app) as client,
        ):
            response = client.post("/api/chat", json={"question": "How many students?"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("network or proxy", response.json()["detail"])
        self.assertNotIn("secret-token-must-not-leak", response.text)


if __name__ == "__main__":
    unittest.main()
