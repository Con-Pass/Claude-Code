from rest_framework import serializers

from conpass.models.meta_key import MetaKey


class ContractMetaKeyListResponseBodySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    label = serializers.CharField()

    class Meta:
        model = MetaKey
        fields = ('id', 'name', 'label')
