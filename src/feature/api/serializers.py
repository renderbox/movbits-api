from rest_framework import serializers

from ..models import FeatureFlag


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ["key", "value"]

    # TODO: the output values of the serializer should be cast to the correct type based on the FeatureFlag.type field and fall back to a string (which it is stored as).
    def to_representation(self, instance):
        result = super().to_representation(instance)
        if instance.type == FeatureFlag.TypeChoices.BOOLEAN:
            result["value"] = instance.value.lower() == "true"
        elif instance.type == FeatureFlag.TypeChoices.INTEGER:
            result["value"] = int(instance.value)
        return result
