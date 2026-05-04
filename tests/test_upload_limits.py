import unittest
import os
from io import BytesIO

from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import RequestEntityTooLarge

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")
os.environ.setdefault("LLM_API_KEY", "test-key")

from teaching_eval.services import _ensure_size_within_limit, _read_uploaded_bytes


class UploadLimitTests(unittest.TestCase):
    def test_declared_size_over_limit_is_rejected(self):
        with self.assertRaises(RequestEntityTooLarge):
            _ensure_size_within_limit(11, 10)

    def test_unknown_size_is_read_with_cap(self):
        uploaded = FileStorage(stream=BytesIO(b"01234567890"), filename="x.txt")

        with self.assertRaises(RequestEntityTooLarge):
            _read_uploaded_bytes(uploaded, 10)

    def test_file_under_limit_is_returned(self):
        uploaded = FileStorage(stream=BytesIO(b"abc"), filename="x.txt")

        self.assertEqual(_read_uploaded_bytes(uploaded, 10), b"abc")


if __name__ == "__main__":
    unittest.main()
