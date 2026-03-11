from rest_framework import serializers

from conpass.models import Client
from conpass.services.user.serializer.user_serializer import UserResponseSerializerEasy
from conpass.views.file.serializer.file_serializer import FileListSerializer
from conpass.views.directory.serializer.directory_serializer import DirectoryResponseSerializer


class ContractListRequestBodySerializer(serializers.Serializer):
    type = serializers.IntegerField()
    directoryId = serializers.IntegerField(required=False, allow_null=True)  # 選択したディレクトリのID(親・子両方)
    showAll = serializers.CharField(required=False, allow_null=True)  # ディレクトリ単位の「全件」検索用
    isGarbage = serializers.CharField(required=False, allow_null=True)  # ゴミ箱表示用
    isOpen = serializers.IntegerField(required=False, allow_null=True)  # 公開フラグ
    isBulkUpload = serializers.IntegerField(required=False, allow_null=True)  # 一括アップロードかどうか
    status = serializers.CharField(allow_blank=True, required=False)
    createdAtFrom = serializers.DateTimeField(allow_null=True, required=False)
    createdAtTo = serializers.DateTimeField(allow_null=True, required=False)
    company = serializers.CharField(allow_blank=True, required=False)
    orderBy = serializers.CharField(allow_blank=True, required=False)
    adoptedVersion = serializers.CharField(allow_null=True, required=False)
    body = serializers.CharField(allow_blank=True, required=False)
    fileName = serializers.CharField(allow_blank=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # メタ情報の検索条件は可変のため項目を動的に設定
        for key in self.initial_data.keys():
            if key.startswith('default'):
                self.fields[key] = serializers.CharField(required=False)
            if key.startswith('defaultDate'):
                self.fields[key] = serializers.DateField(allow_null=True, required=False)
            if key.startswith('defaultAmount'):
                self.fields[key] = serializers.CharField(allow_null=True, required=False)
            if key.startswith('free'):
                self.fields[key] = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate(self, attrs):
        order_by = attrs.get('orderBy')
        suffixes = (' ASC', ' DESC')
        if order_by and not order_by.endswith(suffixes):
            raise serializers.ValidationError("order_byには'order_key ASC'もしくは'order_key DESC'のフォーマットで指定してください")
        return attrs


class ContractListResponseSerializer(serializers.Serializer):
    class ClientModelSerializer(serializers.ModelSerializer):
        class Meta:
            model = Client
            fields = ['name', 'corporateName']

        corporateName = serializers.CharField(source='corporate.name')

    id = serializers.IntegerField()  # ID
    name = serializers.CharField()  # 契約書名
    client = ClientModelSerializer()
    status = serializers.IntegerField()  # ステータス（有効無効）
    endDate = serializers.CharField(source='get_end_date')  # 契約終了日 メタ情報から取る
    noticeDate = serializers.CharField(source='get_notice_date')  # ノーティス メタ情報から取る
    title = serializers.CharField(source='get_title')  # 契約書名 メタ情報から取る
    companiesA = serializers.ListField(source='get_companies_a', allow_empty=True)  # 会社名甲 メタ情報から取る。複数あり
    companiesB = serializers.ListField(source='get_companies_b', allow_empty=True)  # 会社名乙 メタ情報から取る。複数あり
    companiesC = serializers.ListField(source='get_companies_c', allow_empty=True)  # 会社名乙 メタ情報から取る。複数あり
    companiesD = serializers.ListField(source='get_companies_d', allow_empty=True)  # 会社名乙 メタ情報から取る。複数あり
    contractDate = serializers.CharField(source='get_contract_date')  # 契約締結日 メタ情報から取る
    autoUpdate = serializers.CharField(source='get_auto_update')  # 自動更新 メタ情報から取る
    startDate = serializers.CharField(source='get_contract_start_date')  # 契約開始日 メタ情報からとる
    docId = serializers.CharField(source='get_doc_id')  # 管理番号 メタ情報からとる
    relatedDate = serializers.CharField(source='get_related_contract_date')  # 関連契約日 メタ情報からとる
    amount = serializers.CharField(source='get_conpass_amount')  # 金額 メタ情報からとる
    antisocial = serializers.CharField(source='get_antisocial')  # 反社条項 メタ情報から取る
    bpoCorrectionResponse = serializers.IntegerField(source='get_bpo_correction_response')  # BPOデータ補正 対応状況 CorrectionRequestから取る
    files = FileListSerializer(source='get_files', many=True, allow_null=True)
    isOpen = serializers.IntegerField(source='is_open')
    bulkZipPath = serializers.CharField(source='bulk_zip_path')
    directory = DirectoryResponseSerializer(allow_null=True)
    adoptedVersion = serializers.CharField(source='get_adopted_version')  # 採用バージョン contractbodyから取る
    relatedContract = serializers.CharField(source='get_related_contract')  # 関連契約書 メタ情報からとる
    cort = serializers.CharField(source='get_cort')  # 裁判所 メタ情報からとる
    contractType = serializers.CharField(source='get_conpass_contract_type')  # 契約種別 メタ情報からとる
    person = serializers.CharField(source='get_conpass_person')  # 担当者 メタ情報からとる
    freeMetaDatas = serializers.ListField(source='get_free_meta_datas')  # 自由メタ情報 メタ情報からとる
    createdAt = serializers.DateTimeField(source='created_at', format="%Y-%m-%d %H:%M:%S")  # 登録日時
    createdBy = UserResponseSerializerEasy(source='created_by')  # 登録者
    updatedAt = serializers.DateTimeField(source='updated_at', format="%Y-%m-%d %H:%M:%S")  # 更新日時
    updatedBy = UserResponseSerializerEasy(source='updated_by')  # 更新者
