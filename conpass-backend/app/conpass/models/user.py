from enum import Enum, unique
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from conpass.models.constants.statusable import Statusable
from conpass.models import Account, Corporate, Group, Client
from conpass.models.permission_category_key import PermissionCategoryKey
from django.contrib.auth.hashers import make_password


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser, Statusable):
    """
    ConPass利用者
    権限設定は permission で行う
    ログイン名、パスワードが無く、ソーシャルログインを利用している場合もあります
    以下がすべて含まれます。
    - 顧客（Account）に紐づくユーザ
    - 顧客からみた取引先ユーザ
    - 管理側（日本パープル）
    """

    class Type(Enum):
        ACCOUNT = 1  # 顧客（ConPass契約に紐づく利用者）
        CLIENT = 2  # 取引先
        ADMIN = 3  # 管理（日本パープル様）

    login_name = models.CharField(max_length=255, unique=True, verbose_name="ログインID")  # ログインID。メールアドレス形式
    username = models.CharField(max_length=255, verbose_name="名前")  # 日本語名
    division = models.CharField(max_length=255, verbose_name="部署名")  # 部署名
    position = models.CharField(max_length=255, verbose_name="役職")  # 役職
    type = models.IntegerField(default=Type.ACCOUNT.value)  # 種別（顧客、取引先、管理側）
    is_bpo = models.BooleanField(default=False)  # パープル様が顧客ユーザとしてログインし、BPOの操作を行える
    account = models.ForeignKey(Account, on_delete=models.DO_NOTHING,
                                related_name='user_account', blank=True, null=True,
                                default=None)  # 顧客（アカウント）ID typeが顧客の場合
    client = models.ForeignKey(Client, on_delete=models.DO_NOTHING,
                               related_name='user_client', blank=True, null=True,
                               default=None)  # 取引先（連絡先）ID typeが取引先の場合
    corporate = models.ForeignKey(Corporate, on_delete=models.DO_NOTHING, related_name='user_corporate',
                                  blank=True, null=True, default=None)  # 法人ID
    group = models.ManyToManyField(Group, blank=True, related_name='user_group')  # グループID。ない場合もある
    tel = models.CharField(max_length=255, verbose_name="電話番号")  # 電話番号
    memo = models.CharField(max_length=255, verbose_name="備考")  # 備考
    status = models.IntegerField(default=Statusable.Status.ENABLE.value)  # ステータス（有効無効）
    mfa_status = models.IntegerField(default=Statusable.Status.DISABLE.value)  # 2段階認証ステータス（有効無効）
    otp_secret = models.CharField(max_length=32, blank=True, null=True, default=None)  # otp生成用文字列
    is_bpo_admin = models.BooleanField(default=False)  # BPO契約管理者（ワークフローのBPO管理タスク時に担当者に自動設定される）
    created_at = models.DateTimeField(auto_now_add=True)  # 登録日時
    created_by = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='user_created_by', blank=True,
                                   null=True, default=None)  # 登録者
    updated_at = models.DateTimeField(auto_now=True)  # 更新日時
    updated_by = models.ForeignKey('self', on_delete=models.DO_NOTHING, related_name='user_updated_by', blank=True,
                                   null=True, default=None)  # 更新者
    permission_category = models.ForeignKey(PermissionCategoryKey, on_delete=models.SET_NULL,
                                            related_name='user_permission_category_id', blank=True,
                                            null=True, default=None)  # 権限ID

    objects = UserManager()
    USERNAME_FIELD = 'login_name'

    def __str__(self):
        return self.username
