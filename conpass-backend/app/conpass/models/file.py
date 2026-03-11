from enum import Enum, unique
from django.db import models
from conpass.models import User, Account
from conpass.models.constants.statusable import Statusable


class File(models.Model, Statusable):
    """
    GCSにアップロードされているファイル
    """

    class Type(Enum):
        CONTRACT = 1  # 通常の契約書
        TEMPLATE = 2  # 契約書のテンプレート
        PAST = 3  # 過去契約書
        BULK = 4  # 一括アップロード
        CONTRACT_QR = 5  # QRコード付きの契約書
        IMPORTED = 6  # 契約書編集画面からインポートされた契約書
        ETC = 10  # その他：契約書系ではない、とりあえずあげておきたいファイル

    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING, related_name='file_account',
                                blank=True, null=True, default=None)  # アカウントID
    name = models.CharField(max_length=255)  # ファイル名（管理用の名前）
    type = models.IntegerField(Type.CONTRACT.value)  # ファイル種別（契約書、テンプレート、過去契約書、その他）
    description = models.CharField(max_length=255)  # 説明
    url = models.FilePathField(max_length=255)  # GCSの実体へのパス
    size = models.IntegerField(default=0)  # ファイルサイズ（byte）
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='file_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='file_updated_by', blank=True,
                                   null=True, default=None)  # 更新者
    version = models.CharField(max_length=10, blank=True, null=True, default=None)  # インポート時の契約書バージョン名

    def __str__(self):
        return self.name
