from django.contrib.auth import password_validation
from rest_framework import serializers

from conpass.models import User


class SysAdminNewRequestSerializer(serializers.Serializer):
    loginName = serializers.CharField(required=True, max_length=255)
    password = serializers.CharField(required=True)
    username = serializers.CharField(required=True, max_length=255)
    email = serializers.EmailField(required=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_password(self, value):
        user = User(
            login_name=self.initial_data.get('loginName'),
            username=self.initial_data.get('username'),
            email=self.initial_data.get('email'),
        )
        password_validation.validate_password(value, user)
        return value


class SysAdminEditRequestSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    loginName = serializers.CharField(required=True, max_length=255)
    password = serializers.CharField(allow_blank=True, required=False)
    username = serializers.CharField(required=True, max_length=255)
    email = serializers.EmailField(required=True)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_password(self, value):
        if not value:
            return value
        try:
            user = User.objects.get(pk=self.initial_data.get('id'))
        except User.DoesNotExist:
            user = User()
        user.login_name = self.initial_data.get('loginName') or user.login_name
        user.username = self.initial_data.get('username') or user.username
        user.email = self.initial_data.get('email') or user.email
        password_validation.validate_password(value, user)
        return value
