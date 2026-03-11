from rest_framework import serializers


class AccountLinkRequestBodySerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    accessToken = serializers.CharField()
    refreshToken = serializers.CharField()
    providerId = serializers.CharField()
    firebaseUid = serializers.CharField()
    providerDataUid = serializers.CharField()
    photoUrl = serializers.CharField(allow_blank=True, required=False)
    msPhotoData = serializers.CharField(allow_blank=True, required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, data):
        return data
