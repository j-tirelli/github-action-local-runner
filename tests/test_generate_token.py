"""
Unit tests for generate_token.py

Run with:
    pip install PyJWT cryptography pytest
    pytest tests/
"""

import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

# Allow importing from the repo root regardless of working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import jwt

import generate_token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_rsa_private_key_pem() -> str:
    """Generate a throwaway RSA private key in PEM format for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


FAKE_PRIVATE_KEY = _generate_rsa_private_key_pem()
FAKE_APP_ID = "99999"
FIXED_NOW = 1_700_000_000


# ---------------------------------------------------------------------------
# build_app_jwt
# ---------------------------------------------------------------------------

class TestBuildAppJwt(unittest.TestCase):
    def _decode(self, token: str) -> dict:
        """Decode without verification so we can inspect claims."""
        return jwt.decode(token, options={"verify_signature": False})

    def test_iss_is_app_id(self):
        token = generate_token.build_app_jwt(FAKE_APP_ID, FAKE_PRIVATE_KEY, now=FIXED_NOW)
        claims = self._decode(token)
        self.assertEqual(claims["iss"], FAKE_APP_ID)

    def test_iat_is_60_seconds_before_now(self):
        token = generate_token.build_app_jwt(FAKE_APP_ID, FAKE_PRIVATE_KEY, now=FIXED_NOW)
        claims = self._decode(token)
        self.assertEqual(claims["iat"], FIXED_NOW - 60)

    def test_exp_is_600_seconds_after_now(self):
        token = generate_token.build_app_jwt(FAKE_APP_ID, FAKE_PRIVATE_KEY, now=FIXED_NOW)
        claims = self._decode(token)
        self.assertEqual(claims["exp"], FIXED_NOW + 600)

    def test_signature_verifies_with_matching_public_key(self):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        private_key_obj = load_pem_private_key(FAKE_PRIVATE_KEY.encode(), password=None)
        public_key = private_key_obj.public_key()

        token = generate_token.build_app_jwt(FAKE_APP_ID, FAKE_PRIVATE_KEY, now=FIXED_NOW)
        # Disable expiry check — we're testing signature validity, not clock skew
        jwt.decode(token, public_key, algorithms=["RS256"], options={"verify_exp": False})

    def test_uses_current_time_when_now_not_supplied(self):
        import time
        before = int(time.time())
        token = generate_token.build_app_jwt(FAKE_APP_ID, FAKE_PRIVATE_KEY)
        after = int(time.time())
        claims = self._decode(token)
        self.assertGreaterEqual(claims["iat"], before - 60)
        self.assertLessEqual(claims["iat"], after - 60)


# ---------------------------------------------------------------------------
# load_private_key
# ---------------------------------------------------------------------------

class TestLoadPrivateKey(unittest.TestCase):
    def setUp(self):
        # Ensure both env vars are absent before each test
        os.environ.pop("GITHUB_APP_PRIVATE_KEY_PATH", None)
        os.environ.pop("GITHUB_APP_PRIVATE_KEY", None)

    def test_loads_from_file_path(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(FAKE_PRIVATE_KEY)
            f.flush()
            os.environ["GITHUB_APP_PRIVATE_KEY_PATH"] = f.name
            try:
                result = generate_token.load_private_key()
                self.assertEqual(result, FAKE_PRIVATE_KEY)
            finally:
                os.environ.pop("GITHUB_APP_PRIVATE_KEY_PATH", None)
                os.unlink(f.name)

    def test_loads_from_env_var(self):
        os.environ["GITHUB_APP_PRIVATE_KEY"] = FAKE_PRIVATE_KEY
        try:
            result = generate_token.load_private_key()
            self.assertEqual(result, FAKE_PRIVATE_KEY)
        finally:
            os.environ.pop("GITHUB_APP_PRIVATE_KEY", None)

    def test_file_path_takes_priority_over_env_var(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(FAKE_PRIVATE_KEY)
            f.flush()
            os.environ["GITHUB_APP_PRIVATE_KEY_PATH"] = f.name
            os.environ["GITHUB_APP_PRIVATE_KEY"] = "should-not-be-used"
            try:
                result = generate_token.load_private_key()
                self.assertEqual(result, FAKE_PRIVATE_KEY)
            finally:
                os.environ.pop("GITHUB_APP_PRIVATE_KEY_PATH", None)
                os.environ.pop("GITHUB_APP_PRIVATE_KEY", None)
                os.unlink(f.name)

    def test_exits_when_file_not_found(self):
        os.environ["GITHUB_APP_PRIVATE_KEY_PATH"] = "/nonexistent/key.pem"
        try:
            with self.assertRaises(SystemExit):
                generate_token.load_private_key()
        finally:
            os.environ.pop("GITHUB_APP_PRIVATE_KEY_PATH", None)

    def test_exits_when_neither_source_set(self):
        with self.assertRaises(SystemExit):
            generate_token.load_private_key()


# ---------------------------------------------------------------------------
# api_post
# ---------------------------------------------------------------------------

class TestApiPost(unittest.TestCase):
    def _make_mock_response(self, body: dict):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(body).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_returns_parsed_json_on_success(self):
        body = {"token": "ghs_abc123"}
        with patch("urllib.request.urlopen", return_value=self._make_mock_response(body)):
            result = generate_token.api_post("https://api.github.com/test", "bearer-token")
        self.assertEqual(result, body)

    def test_sets_correct_headers(self):
        body = {"token": "ghs_abc123"}
        with patch("urllib.request.urlopen", return_value=self._make_mock_response(body)) as mock_open:
            generate_token.api_post("https://api.github.com/test", "my-token")
            req = mock_open.call_args[0][0]
            self.assertEqual(req.get_header("Authorization"), "Bearer my-token")
            self.assertEqual(req.get_header("Accept"), "application/vnd.github+json")
            self.assertEqual(req.get_header("X-github-api-version"), "2022-11-28")

    def test_uses_post_method(self):
        body = {"token": "ghs_abc123"}
        with patch("urllib.request.urlopen", return_value=self._make_mock_response(body)) as mock_open:
            generate_token.api_post("https://api.github.com/test", "my-token")
            req = mock_open.call_args[0][0]
            self.assertEqual(req.get_method(), "POST")

    def test_exits_on_http_error(self):
        error = urllib.error.HTTPError(
            url="https://api.github.com/test",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"message":"Bad credentials"}'),
        )
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(SystemExit):
                generate_token.api_post("https://api.github.com/test", "bad-token")


# ---------------------------------------------------------------------------
# get_registration_token (integration of the above)
# ---------------------------------------------------------------------------

class TestGetRegistrationToken(unittest.TestCase):
    def test_calls_correct_urls_and_returns_token(self):
        installation_response = {"token": "ghs_installation_token"}
        registration_response = {"token": "AABBCC_registration_token"}

        call_responses = iter([installation_response, registration_response])

        with patch.object(generate_token, "api_post", side_effect=lambda url, _: next(call_responses)) as mock_post:
            result = generate_token.get_registration_token(
                app_id=FAKE_APP_ID,
                installation_id="67890",
                repo_path="owner/repo",
                private_key=FAKE_PRIVATE_KEY,
            )

        self.assertEqual(result, "AABBCC_registration_token")

        first_call_url = mock_post.call_args_list[0][0][0]
        second_call_url = mock_post.call_args_list[1][0][0]
        self.assertIn("/app/installations/67890/access_tokens", first_call_url)
        self.assertIn("/repos/owner/repo/actions/runners/registration-token", second_call_url)

    def test_installation_token_passed_to_second_call(self):
        installation_response = {"token": "ghs_installation_token"}
        registration_response = {"token": "reg_token"}

        call_responses = iter([installation_response, registration_response])

        with patch.object(generate_token, "api_post", side_effect=lambda url, tok: next(call_responses)) as mock_post:
            generate_token.get_registration_token(
                app_id=FAKE_APP_ID,
                installation_id="67890",
                repo_path="owner/repo",
                private_key=FAKE_PRIVATE_KEY,
            )

        second_call_token = mock_post.call_args_list[1][0][1]
        self.assertEqual(second_call_token, "ghs_installation_token")


# ---------------------------------------------------------------------------
# main() — env var validation
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def setUp(self):
        for var in ("GITHUB_APP_ID", "GITHUB_APP_INSTALLATION_ID", "REPO_PATH",
                    "GITHUB_APP_PRIVATE_KEY", "GITHUB_APP_PRIVATE_KEY_PATH"):
            os.environ.pop(var, None)

    def _set_env(self, **kwargs):
        for k, v in kwargs.items():
            os.environ[k] = v

    def tearDown(self):
        self.setUp()

    def test_exits_when_app_id_missing(self):
        self._set_env(GITHUB_APP_INSTALLATION_ID="1", REPO_PATH="o/r", GITHUB_APP_PRIVATE_KEY=FAKE_PRIVATE_KEY)
        with self.assertRaises(SystemExit):
            generate_token.main()

    def test_exits_when_installation_id_missing(self):
        self._set_env(GITHUB_APP_ID="1", REPO_PATH="o/r", GITHUB_APP_PRIVATE_KEY=FAKE_PRIVATE_KEY)
        with self.assertRaises(SystemExit):
            generate_token.main()

    def test_exits_when_repo_path_missing(self):
        self._set_env(GITHUB_APP_ID="1", GITHUB_APP_INSTALLATION_ID="2", GITHUB_APP_PRIVATE_KEY=FAKE_PRIVATE_KEY)
        with self.assertRaises(SystemExit):
            generate_token.main()

    def test_prints_token_to_stdout(self):
        self._set_env(
            GITHUB_APP_ID=FAKE_APP_ID,
            GITHUB_APP_INSTALLATION_ID="67890",
            REPO_PATH="owner/repo",
            GITHUB_APP_PRIVATE_KEY=FAKE_PRIVATE_KEY,
        )
        with patch.object(generate_token, "get_registration_token", return_value="my_reg_token"):
            with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                generate_token.main()
                self.assertEqual(mock_stdout.getvalue(), "my_reg_token")


if __name__ == "__main__":
    unittest.main()
