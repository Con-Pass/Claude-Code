from rest_framework import serializers
from conpass.models import Contract, User
from conpass.models.constants.contractmetakeyidable import ContractMetaKeyIdable
from conpass.models.constants.statusable import Statusable


class ContractBriefInfoSerializer(serializers.ModelSerializer):
    meta_data = serializers.SerializerMethodField(read_only=True)
    directory = serializers.SerializerMethodField(read_only=True)
    file_id = serializers.SerializerMethodField(read_only=True)
    file_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            'id',
            'name',
            'meta_data',
            'directory',
            'file_id',
            'file_name'
        ]

    def to_representation(self, instance):
        instance.meta_data_dict = {}
        wheres = {
            'status': Statusable.Status.ENABLE.value,
        }
        # メタ情報が複数あるものはpdf読み込み時のエラーなので簡易情報では上書き
        for md in instance.meta_data_contract.filter(**wheres).order_by('-value').all():
            if md.key.id == ContractMetaKeyIdable.MetaKeyId.CONTRACTENDDATE.value:
                instance.meta_data_dict[md.key.name] = md.date_value
            elif md.key.id == ContractMetaKeyIdable.MetaKeyId.CONPASS_PERSON.value:
                instance.meta_data_dict[md.key.name] = self.get_username_by_id(md.value) if md.value else ""
            else:
                instance.meta_data_dict[md.key.name] = md.value

        try:
            file = instance.file.all()[0]
            instance.file_obj = file
        except IndexError:
            instance.file_obj = None

        return super().to_representation(instance)

    def get_username_by_id(self, user_id):
        user = User.objects.filter(id=user_id).first()
        return user.username if user else ""

    def get_meta_data(self, obj):
        return obj.meta_data_dict

    def get_directory(self, obj):
        return obj.directory.name if obj.directory else None

    def get_file_id(self, obj):
        return obj.file_obj.id if obj.file_obj else None

    def get_file_name(self, obj):
        return obj.file_obj.name if obj.file_obj else None
