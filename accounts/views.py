from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated

from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from .serializers import (
    AuthResponseSerializer,
    LoginSerializer,
    LogoutRequestSerializer,
    MessageResponseSerializer,
    ProfileSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=UserSerializer,
        responses={201: AuthResponseSerializer},
        description="Create a new account and return JWT access/refresh tokens.",
    )
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Registration successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: AuthResponseSerializer},
        description="Authenticate with email + password and return JWT access/refresh tokens.",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "Login successful",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                },
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutRequestSerializer,
        responses={200: MessageResponseSerializer},
        description="Blacklist a refresh token so it can no longer be used to obtain new access tokens.",
    )
    def post(self, request):
        try:
            refresh_token = request.data["refresh"]

            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                {"message": "Logout successful"},
                status=status.HTTP_200_OK
            )

        except Exception:
            return Response(
                {"error": "Invalid refresh token"},
                status=status.HTTP_400_BAD_REQUEST
            )


class MeView(APIView):
    """
    GET  /api/me/  -> current user's profile
    PATCH /api/me/ -> update current user's profile (age, gender, email, name)

    Lets the Flutter app fetch/update the logged-in user's profile
    without needing the user's id, and without touching admin-only fields.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProfileSerializer}, description="Get the authenticated user's profile.")
    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    @extend_schema(
        request=ProfileSerializer,
        responses={200: ProfileSerializer},
        description="Partially update the authenticated user's profile.",
    )
    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
