from rest_framework import serializers

from conpass.models import AccountStorageSummary


class AccountStorageSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountStorageSummary
        fields = [
            'account_id',
            'file_size_total',
            'file_num',
            'cycle',
            'date_from',
            'date_to',
            'created_at',
            'updated_at',
        ]
