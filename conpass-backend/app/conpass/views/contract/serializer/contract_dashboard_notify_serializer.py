from rest_framework import serializers

from conpass.views.contract.serializer.contract_item_serializer import ContractItemResponseSerializer, \
    ContractMetaDataResponseSerializer


class ContractWithMetaRequestBodySerializer(serializers.Serializer):
    tags = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
    )


class ContractRenewalListResponseSerializer(serializers.Serializer):
    contract = ContractItemResponseSerializer()
    metaList = serializers.ListField(
        child=ContractMetaDataResponseSerializer(),
        allow_empty=True,
        source='meta_list'
    )


class ContractRenewalListResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = serializers.ListField(
        child=ContractRenewalListResponseSerializer(),
        allow_empty=True
    )
