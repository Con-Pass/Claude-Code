from rest_framework import serializers


class SysAdminDeleteRequestSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, required=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
