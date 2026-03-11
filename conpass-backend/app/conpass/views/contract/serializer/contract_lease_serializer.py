from rest_framework import serializers
from conpass.models import LeaseKey


class ContractLeaseNameSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta:
        model = LeaseKey
        fields = ('name',)
