from rest_framework import serializers

from conpass.models import User


class SysAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'login_name',
            'username',
            'email',
            'last_login',
            'created_at',
            'updated_at',
        ]

    last_login = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass
