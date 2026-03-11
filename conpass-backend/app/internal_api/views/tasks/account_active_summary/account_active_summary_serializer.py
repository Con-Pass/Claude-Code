from rest_framework import serializers


class PrivateApiExecuteAccountActiveSummaryDailyRequestBodySerializer(serializers.Serializer):
    dateString = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class PrivateApiExecuteAccountActiveSummaryMonthlyRequestBodySerializer(serializers.Serializer):
    monthString = serializers.CharField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs
