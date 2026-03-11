import unicodedata
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from conpass.views.ip_address.serializer.ip_address_detail_serializer import IpAddressDetailResponseSerializer
from django.core.validators import validate_ipv4_address


class IpAddressEditRequestBodySerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True, required=False)  # ID
    ip_address = serializers.CharField(allow_blank=False, required=True,
                                       error_messages={'blank': 'IPアドレス(IPv4)を入力してください。'})  # IPアドレス
    ip_address_end = serializers.CharField(allow_blank=True, required=False)  # IPアドレス
    remarks = serializers.CharField(allow_blank=True, required=False, default='')  # 備考
    status = serializers.IntegerField()  # ステータス

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_ip_address(self, value):
        value = unicodedata.normalize('NFKC', value)  # 全角を半角に変換
        try:
            validate_ipv4_address(value)  # IPアドレスのバリデーション
        except ValidationError:
            raise ValidationError("'{}'は有効なIPアドレス(IPv4)ではありません。".format(value))
        last_part = int(value.split('.')[-1])  # IPアドレスの最後の数値
        ip_address_end = self.initial_data.get('ip_address_end')
        if ip_address_end:
            ip_address_end = unicodedata.normalize('NFKC', ip_address_end)  # 全角を半角に変換
            try:
                number = int(ip_address_end)
                if not last_part < number <= 255:
                    raise ValidationError(
                        "並びのIPアドレスを登録する場合は'{}'より大きい255までの数値を入力してください。".format(last_part))
            except ValueError:
                raise ValidationError("並びのIPアドレスを登録する場合は'{}'より大きい255までの数値を入力してください。".format(last_part))
        return value


class IpAddressEditResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = IpAddressDetailResponseSerializer()
