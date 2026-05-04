import unittest
import os
from unittest.mock import Mock, patch

import requests

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")
os.environ.setdefault("LLM_API_KEY", "test-key")

from teaching_eval.llm_client import LLMClient


class LLMClientRetryTests(unittest.TestCase):
    def test_generate_retries_transient_timeout(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        client = LLMClient("key", "https://example.test/chat", "model")

        with patch("teaching_eval.llm_client.requests.post", side_effect=[requests.Timeout("boom"), response]) as post:
            with patch("teaching_eval.llm_client.time.sleep") as sleep:
                result = client.generate("system", "user", timeout=1)

        self.assertEqual(result, "ok")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_generate_does_not_retry_auth_error(self):
        http_response = Mock()
        http_response.status_code = 401
        error = requests.HTTPError("unauthorized", response=http_response)
        response = Mock()
        response.raise_for_status.side_effect = error
        client = LLMClient("key", "https://example.test/chat", "model")

        with patch("teaching_eval.llm_client.requests.post", return_value=response) as post:
            with patch("teaching_eval.llm_client.time.sleep") as sleep:
                with self.assertRaises(requests.HTTPError):
                    client.generate("system", "user", timeout=1)

        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
