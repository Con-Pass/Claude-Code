from rest_framework import serializers


class SysAdminListRequestSerializer(serializers.Serializer):
    userName = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
