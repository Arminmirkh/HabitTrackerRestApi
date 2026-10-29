from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Used for registration and profile display/update.

    Fields are explicitly whitelisted (never "__all__") -- exposing
    is_staff / is_superuser / is_active / groups / user_permissions
    as writable would let any client self-promote to admin on
    registration.
    """
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "first_name", "last_name", "age", "gender"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class ProfileSerializer(serializers.ModelSerializer):
    """Read/update for the authenticated user's own profile (no password field)."""

    # Computed fresh from real HabitRecord history on every read, same
    # reasoning as Habit.streak in habits.serializers.HabitSerializer --
    # a plain cached field would only update on the next check-in and
    # could show a stale nonzero value after a day with no check-ins at all.
    overall_streak = serializers.SerializerMethodField()
    overall_best_streak = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "age", "gender",
            "overall_streak", "overall_best_streak",
        ]
        read_only_fields = ["id", "username"]

    def _live_overall_streak(self, obj):
        if not hasattr(obj, "_overall_streak_result_cache"):
            from habits.streaks import calculate_overall_streak
            obj._overall_streak_result_cache = calculate_overall_streak(obj)
        return obj._overall_streak_result_cache

    def get_overall_streak(self, obj) -> int:
        result = self._live_overall_streak(obj)
        if obj.overall_streak != result["current_streak"]:
            User.objects.filter(pk=obj.pk).update(overall_streak=result["current_streak"])
            obj.overall_streak = result["current_streak"]
        return result["current_streak"]

    def get_overall_best_streak(self, obj) -> int:
        result = self._live_overall_streak(obj)
        if obj.overall_best_streak != result["longest_streak"]:
            User.objects.filter(pk=obj.pk).update(overall_best_streak=result["longest_streak"])
            obj.overall_best_streak = result["longest_streak"]
        return result["longest_streak"]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            raise serializers.ValidationError(
                "Both email and password are required."
            )

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")

        if not user.check_password(password):
            raise serializers.ValidationError("Incorrect password.")

        data["user"] = user
        return data


class AuthUserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()


class AuthResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user = AuthUserSummarySerializer()
    access = serializers.CharField(help_text="Short-lived JWT access token.")
    refresh = serializers.CharField(help_text="Long-lived JWT refresh token.")


class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="A valid, non-blacklisted refresh token to blacklist.")


class MessageResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
