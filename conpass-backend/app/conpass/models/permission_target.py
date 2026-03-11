from enum import Enum

from django.db import models
from conpass.models import User
from conpass.models.constants.statusable import Statusable


class PermissionTarget(models.Model, Statusable):
    """
    ユーザの権限の項目名マスタ
    "契約書閲覧"であれば、契約書の閲覧をする機能がすべて対象になる
    """

    class Target(Enum):
        UPLOAD_SIGNED_CONTRACT = 1  # 締結済み契約書アップロード
        UPLOAD_CONTRACT_TEMPLATE = 2  # 契約書テンプレートアップロード
        DOWNLOAD_CONTRACT = 3  # 契約書ダウンロード
        DISP_SIGNED_CONTRACT_DETAIL = 4  # 締結済み契約書詳細表示
        DISP_USER_SETTING = 5  # ユーザー管理
        BPO_REQUEST = 6  # BPO依頼
        EDIT_META_SETTING = 7  # 契約書メタ情報の管理
        # CREATE_NEW_CONTRACT = 8 # 新規契約書作成（不要になりました）
        DISP_DIRECTORY_SETTING = 9  # フォルダ管理
        DELETE_CONTRACT = 10  # 契約書削除
        DISP_WORKFLOW_SETTING = 11  # ワークフロー管理
        DISP_CLIENT_SETTING = 12  # 連絡先管理
        IP_ADDRESS_RESTRICTION = 13  # IPアドレス制限管理
        EDIT_META_DATA = 14 #メタ情報編集

    name = models.CharField(max_length=255)  # 権限指定対象
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    sort_id = models.IntegerField(blank=True, null=True, default=None)
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='permission_target_created_by', blank=True, null=True,
                                   default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey(User, on_delete=models.DO_NOTHING,
                                   related_name='permission_target_updated_by', blank=True, null=True,
                                   default=None)  # 更新者

    def __str__(self):
        return self.name
