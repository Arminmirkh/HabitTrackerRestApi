from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class RegisterViewTests(APITestCase):
    url = reverse("register")

    def valid_payload(self, **overrides):
        payload = {
            "username": "alice",
            "email": "alice@example.com",
            "password": "S3curePass!23",
            "age": 22,
            "gender": "F",
        }
        payload.update(overrides)
        return payload

    def test_register_creates_user_and_returns_tokens(self):
        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="alice@example.com").exists())
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        # Password must never be echoed back in the response.
        self.assertNotIn("password", response.data["user"])

    def test_register_rejects_duplicate_email(self):
        User.objects.create_user(username="existing", email="alice@example.com", password="whatever123")

        response = self.client.post(self.url, self.valid_payload(username="alice2"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(email="alice@example.com").count(), 1)

    def test_register_rejects_password_shorter_than_min_length(self):
        response = self.client.post(self.url, self.valid_payload(password="short"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="alice@example.com").exists())

    def test_register_ignores_attempt_to_self_promote_to_staff(self):
        """
        UserSerializer explicitly whitelists fields (never "__all__"), so
        is_staff/is_superuser must be silently ignored, not accepted.
        """
        response = self.client.post(
            self.url, self.valid_payload(is_staff=True, is_superuser=True), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="alice@example.com")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_register_accepts_syntactically_odd_but_valid_email(self):
        """
        Documents current behavior: Django's EmailValidator only checks
        format, not that the domain/TLD actually exists or receives mail.
        This is expected to pass today.
        """
        response = self.client.post(self.url, self.valid_payload(email="ar@aa.comm"), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_rejects_malformed_email(self):
        response = self.client.post(self.url, self.valid_payload(email="not-an-email"), format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginViewTests(APITestCase):
    url = reverse("login")

    def setUp(self):
        self.user = User.objects.create_user(
            username="bob", email="bob@example.com", password="CorrectHorse1!"
        )

    def test_login_succeeds_with_correct_credentials(self):
        response = self.client.post(
            self.url, {"email": "bob@example.com", "password": "CorrectHorse1!"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_fails_with_wrong_password(self):
        response = self.client.post(
            self.url, {"email": "bob@example.com", "password": "WrongPassword"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_fails_for_unknown_email(self):
        response = self.client.post(
            self.url, {"email": "nobody@example.com", "password": "whatever"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_is_case_insensitive_on_email(self):
        response = self.client.post(
            self.url, {"email": "BOB@EXAMPLE.COM", "password": "CorrectHorse1!"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class MeViewTests(APITestCase):
    url = reverse("me")

    def setUp(self):
        self.user = User.objects.create_user(
            username="carol", email="carol@example.com", password="AnotherPass1!", age=30, gender="F"
        )
        self.client.force_authenticate(user=self.user)

    def test_get_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_own_profile(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "carol@example.com")
        self.assertIn("overall_streak", response.data)

    def test_patch_updates_allowed_fields(self):
        response = self.client.patch(self.url, {"first_name": "Carol"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Carol")

    def test_patch_cannot_change_username(self):
        """username is read_only on ProfileSerializer -- verify it can't be changed here."""
        response = self.client.patch(self.url, {"username": "hacked"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "carol")


class LogoutViewTests(APITestCase):
    url = reverse("logout")

    def setUp(self):
        self.user = User.objects.create_user(
            username="dave", email="dave@example.com", password="YetAnother1!"
        )
        self.client.force_authenticate(user=self.user)

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)

        response = self.client.post(self.url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # A blacklisted refresh token must no longer mint new access tokens.
        refresh_url = reverse("token-refresh")
        refresh_response = self.client.post(refresh_url, {"refresh": str(refresh)}, format="json")
        self.assertEqual(refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_token_returns_400(self):
        response = self.client.post(self.url, {"refresh": "not-a-real-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
