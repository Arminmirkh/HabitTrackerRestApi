from rest_framework import serializers


class GenerateHabitsRequestSerializer(serializers.Serializer):
    goal = serializers.CharField(max_length=500, allow_blank=False)


class SuggestedHabitSerializer(serializers.Serializer):
    title = serializers.CharField()
    frequency = serializers.ChoiceField(choices=["daily", "weekly", "monthly"])
    difficulty = serializers.ChoiceField(choices=["easy", "medium", "hard"])
    reason = serializers.CharField()


class GenerateHabitsResponseSerializer(serializers.Serializer):
    goal = serializers.CharField()
    habits = SuggestedHabitSerializer(many=True)
