from rest_framework import serializers


class SysAdminDetailRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
