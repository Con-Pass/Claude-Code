from rest_framework import serializers

from conpass.models.gmo_sign import GmoSign, GmoSignSigner


class GmoSignSignerSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = GmoSignSigner
        fields = ['id', 'email', 'name', 'order', 'status', 'status_display',
                  'signed_at', 'created_at']
        read_only_fields = ['id', 'status', 'signed_at', 'created_at']


class GmoSignSerializer(serializers.ModelSerializer):
    signers = GmoSignSignerSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = GmoSign
        fields = ['id', 'contract', 'workflow', 'gmo_document_id', 'status',
                  'status_display', 'sent_at', 'signed_at', 'signers',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'gmo_document_id', 'status', 'sent_at',
                           'signed_at', 'created_at', 'updated_at']


class GmoSignCreateSerializer(serializers.Serializer):
    contract_id = serializers.IntegerField()
    signers = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
    )

    def validate_signers(self, value):
        for signer in value:
            if 'email' not in signer or 'name' not in signer:
                raise serializers.ValidationError(
                    "各署名者にはemailとnameが必要です"
                )
        return value


class GmoSignSendSerializer(serializers.Serializer):
    gmo_sign_id = serializers.IntegerField()
