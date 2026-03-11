from rest_framework import serializers


class UpdateContractRenewNotifySerializer(serializers.Serializer):
    contract_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={
            'empty': '契約書を選択してください。'
        }
    )
