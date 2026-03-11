from rest_framework import serializers


class ContractSearchSettingRequestBodySerializer(serializers.Serializer):
    type = serializers.IntegerField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractSearchSettingEditRequestBodySerializer(serializers.Serializer):
    type = serializers.IntegerField()
    defaultList = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )
    freeList = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )
    checkedStatus = serializers.BooleanField()
    checkedCreatedAt = serializers.BooleanField()
    checkedIsOpen = serializers.BooleanField()
    checkedCompany = serializers.BooleanField()

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        return attrs


class ContractSearchMetaItem(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    checked = serializers.BooleanField(default=False)
    isDate = serializers.BooleanField(default=False)


class ContractSearchItem(serializers.Serializer):
    checked = serializers.BooleanField(default=False)
    value = serializers.CharField(allow_blank=True, required=False)
    fromValue = serializers.CharField(allow_blank=True, required=False)
    toValue = serializers.CharField(allow_blank=True, required=False)


class ContractSearchSettingResponseSerializer(serializers.Serializer):
    defaultList = ContractSearchMetaItem(many=True, source="default_list")
    freeList = ContractSearchMetaItem(many=True, source="free_list")
    status = ContractSearchItem()
    createdAt = ContractSearchItem(source="created_at")
    isOpen = ContractSearchItem(source="is_open")
    company = ContractSearchItem()
    fileName = ContractSearchItem(source="file_name")
    pageSize = serializers.IntegerField(source="page_size", required=False, default=None)


class ContractSearchSettingResponseBodySerializer(serializers.Serializer):
    """
    response body serializer
    """

    def __init__(self, data):
        """
        DBのクエリ結果を受け取って、APIのレスポンス形式に整形する
        instanceがシリアライズの対象になる
        """
        self.instance = {"response": data}

    response = ContractSearchSettingResponseSerializer()
