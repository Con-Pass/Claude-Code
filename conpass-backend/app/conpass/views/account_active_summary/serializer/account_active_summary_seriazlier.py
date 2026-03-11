from rest_framework import serializers

from conpass.models import AccountActiveSummary


class AccountActiveSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountActiveSummary
        fields = [
            'account_id',
            'active_contracts_count',
            'cycle',
            'date_from',
            'date_to',
            'created_at',
            'updated_at',
        ]
