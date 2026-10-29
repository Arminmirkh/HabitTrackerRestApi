from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .ai_service import AIHabitGenerationError, generate_habits
from .serializers import GenerateHabitsRequestSerializer, GenerateHabitsResponseSerializer


class GenerateHabitsView(APIView):
    """
    POST /api/ai/generate-habits/
    Body: {"goal": "run a 10k"}

    Calls the AI model to turn a free-text goal into 3-5 suggested
    habits and returns them directly. Nothing is saved to the
    database -- use POST /api/habits/bulk-create/ (or individual
    POST /api/habits/) if the user wants to keep any of the results.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GenerateHabitsRequestSerializer,
        responses={200: GenerateHabitsResponseSerializer},
        description="Generate AI-suggested habits for a free-text goal. Nothing is persisted.",
    )
    def post(self, request):
        req_serializer = GenerateHabitsRequestSerializer(data=request.data)
        req_serializer.is_valid(raise_exception=True)
        goal_text = req_serializer.validated_data["goal"]

        try:
            result = generate_habits(goal_text)
        except AIHabitGenerationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result, status=status.HTTP_200_OK)
