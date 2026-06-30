import unittest
from types import SimpleNamespace

from app.routes import auth


class AuthSecurityTests(unittest.TestCase):
    def test_generate_otp_is_six_digits(self):
        otp = auth._generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def test_generate_otp_is_not_fixed(self):
        otps = {auth._generate_otp() for _ in range(20)}
        self.assertGreater(len(otps), 1)

    def test_is_expired_rejects_old_timestamp(self):
        self.assertTrue(auth._is_expired("2000-01-01T00:00:00Z"))

    def test_hash_email_does_not_expose_raw_email(self):
        email = "User.Example@example.com"
        digest = auth._hash_email(email)
        self.assertEqual(len(digest), 16)
        self.assertNotIn("User", digest)
        self.assertNotIn("example.com", digest)

    def test_redis_login_key_does_not_expose_raw_email_or_ip(self):
        request = SimpleNamespace(
            headers={"x-forwarded-for": "203.0.113.9"},
            client=SimpleNamespace(host="127.0.0.1"),
        )
        key = auth._redis_login_key("user@example.com", request)
        self.assertTrue(key.startswith("auth:login_fail:"))
        self.assertNotIn("user@example.com", key)
        self.assertNotIn("203.0.113.9", key)


if __name__ == "__main__":
    unittest.main()
