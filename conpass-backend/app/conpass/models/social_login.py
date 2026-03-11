from enum import Enum, unique
from django.db import models

from conpass.models.constants.statusable import Statusable


class SocialLogin(models.Model, Statusable):
    """
    ソーシャルログイン
    当初はgoogle/microsoft
    firebaseを使う予定です
    """

    @unique
    class Type(Enum):
        GOOGLE = 1
        MICROSOFT = 2

    user = models.ForeignKey('conpass.User', on_delete=models.CASCADE, related_name='socoal_login_user')  # ユーザID
    access_token = models.TextField()  # ソーシャルログイン用トークン
    refresh_token = models.TextField()  # リフレッシュ用トークン
    client_id = models.CharField(max_length=512)  # クライアントID
    type = models.IntegerField()  # ソーシャルログイン種別 google/microsoft
    provider_id = models.CharField(max_length=64, null=True)
    firebase_uid = models.CharField(max_length=512, null=True)
    provider_data_uid = models.CharField(max_length=512, null=True)
    photo_url = models.CharField(max_length=512, null=True)
    ms_photo_data = models.TextField(null=True)
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    created_at = models.DateTimeField()  # 登録日時
    created_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='social_login_created_by', blank=True, null=True, default=None)  # 登録者
    updated_at = models.DateTimeField()  # 更新日時
    updated_by = models.ForeignKey('conpass.User', on_delete=models.DO_NOTHING,
                                   related_name='social_login_updated_by', blank=True, null=True, default=None)  # 更新者

    def __str__(self):
        return self.access_token
