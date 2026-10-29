import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import User
from .ai_service import AIHabitGenerationError, generate_habits


def make_groq_response(payload: dict):
    """Builds a fake Groq ChatCompletion response carrying `payload` as JSON text."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    return response


class GenerateHabitsServiceTests(TestCase):
    """
    Unit tests for ai.ai_service.generate_habits with the Groq client
    mocked out -- these must never hit the real network/API.
    """

    @override_settings(GROQ_API_KEY="")
    def test_raises_when_api_key_missing(self):
        with self.assertRaises(AIHabitGenerationError):
            generate_habits("run a 10k")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_returns_cleaned_habits_on_valid_response(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        mock_client.chat.completions.create.return_value = make_groq_response({
            "goal": "Run a 10k",
            "habits": [
                {"title": "Walk 15 min", "frequency": "daily", "difficulty": "easy", "reason": "Builds the habit."},
                {"title": "Jog 2x/week", "frequency": "weekly", "difficulty": "medium", "reason": "Builds distance."},
            ],
        })

        result = generate_habits("run a 10k")

        self.assertEqual(result["goal"], "Run a 10k")
        self.assertEqual(len(result["habits"]), 2)
        self.assertEqual(result["habits"][0]["title"], "Walk 15 min")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_drops_malformed_habit_entries_but_keeps_valid_ones(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        mock_client.chat.completions.create.return_value = make_groq_response({
            "goal": "Read more",
            "habits": [
                {"title": "Read 10 pages", "frequency": "daily", "difficulty": "easy"},
                {"title": ""},  # no title -- should be dropped
                "not even a dict",  # should be dropped
            ],
        })

        result = generate_habits("read more")

        self.assertEqual(len(result["habits"]), 1)
        self.assertEqual(result["habits"][0]["title"], "Read 10 pages")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_invalid_frequency_and_difficulty_fall_back_to_defaults(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        mock_client.chat.completions.create.return_value = make_groq_response({
            "goal": "Save money",
            "habits": [
                {"title": "Track spending", "frequency": "biweekly", "difficulty": "extreme"},
            ],
        })

        result = generate_habits("save money")

        self.assertEqual(result["habits"][0]["frequency"], "daily")
        self.assertEqual(result["habits"][0]["difficulty"], "medium")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_raises_on_non_json_response(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        response = MagicMock()
        response.choices = [MagicMock(message=MagicMock(content="not json at all"))]
        mock_client.chat.completions.create.return_value = response

        with self.assertRaises(AIHabitGenerationError):
            generate_habits("anything")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_raises_when_response_has_no_habit_list(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        mock_client.chat.completions.create.return_value = make_groq_response({"goal": "x", "habits": []})

        with self.assertRaises(AIHabitGenerationError):
            generate_habits("anything")

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.ai_service.Groq")
    def test_wraps_network_exceptions(self, mock_groq_cls):
        mock_client = mock_groq_cls.return_value
        mock_client.chat.completions.create.side_effect = ConnectionError("boom")

        with self.assertRaises(AIHabitGenerationError):
            generate_habits("anything")


class GenerateHabitsViewTests(APITestCase):
    url = reverse("generate-habits")

    def setUp(self):
        self.user = User.objects.create_user(
            username="eve", email="eve@example.com", password="TestPass123!"
        )
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.post(self.url, {"goal": "run a 10k"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_blank_goal(self):
        response = self.client.post(self.url, {"goal": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(GROQ_API_KEY="fake-key-for-tests")
    @patch("ai.views.generate_habits")
    def test_returns_habits_from_service_on_success(self, mock_generate):
        mock_generate.return_value = {
            "goal": "Run a 10k",
            "habits": [{"title": "Walk daily", "frequency": "daily", "difficulty": "easy", "reason": "Start small."}],
        }

        response = self.client.post(self.url, {"goal": "run a 10k"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["goal"], "Run a 10k")
        mock_generate.assert_called_once_with("run a 10k")

    @patch("ai.views.generate_habits")
    def test_returns_502_when_ai_service_fails(self, mock_generate):
        mock_generate.side_effect = AIHabitGenerationError("AI request failed")

        response = self.client.post(self.url, {"goal": "run a 10k"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("error", response.data)

    @patch("ai.views.generate_habits")
    def test_nothing_is_persisted_by_this_endpoint(self, mock_generate):
        """Docs say this endpoint never saves to the DB -- verify no Habit is created."""
        from habits.models import Habit

        mock_generate.return_value = {
            "goal": "Run a 10k",
            "habits": [{"title": "Walk daily", "frequency": "daily", "difficulty": "easy", "reason": "x"}],
        }

        self.client.post(self.url, {"goal": "run a 10k"}, format="json")

        self.assertEqual(Habit.objects.count(), 0)
