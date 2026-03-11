import csv
import io
import random
import string
import traceback
from logging import getLogger

import django.db
from django.db.models import Q
from django.contrib.auth import password_validation
from django.contrib.auth.hashers import make_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.utils import DatabaseError
from django.utils.timezone import make_aware

from conpass.models import User, Client, Account, PermissionTarget, PermissionCategory, PermissionCategoryKey, Permission
from conpass.models.constants import Statusable
from conpass.services.user.user_service import UserService
from conpass.mailer.user_mailer import UserMailer

import datetime

from rest_framework import serializers
from rest_framework import status
from rest_framework.response import Response

logger = getLogger(__name__)


class UserClientCsvImporter:
    filed_names = [
        "メールアドレス",
        "名前",
        "部署名",
        "役職",
        "電話番号",
        "備考",
    ]

    field_mapping = {
        "メールアドレス": "login_name",
        "名前": "username",
        "部署名": "division",
        "役職": "position",
        "電話番号": "tel",
        "備考": "memo",
    }

    field_reverse_mapping = {
        v: k for k, v in field_mapping.items()
    }

    def __init__(self, contents: str, client: Client, operated_by: User):
        self._contents = contents
        self._client = client
        self._operated_by = operated_by
        self._validated = False
        self.errors = []

    def import_users(self):
        if not self._validated:
            raise self.NotValidatedError

        reader = csv.DictReader(io.StringIO(self._contents))
        # 登録するユーザーは連絡先（type=CLIENT）のため、login_nameの末尾にclient_idをつけて保存する
        for row in reader:
            user = User(
                account_id=self._client.provider_account_id,
                client_id=self._client.id,
                login_name=f"{row['メールアドレス']}:{self._client.id}",
                email=row['メールアドレス'],
                username=row['名前'],
                division=row['部署名'],
                position=row['役職'],
                tel=row['電話番号'],
                memo=row['備考'],
                type=User.Type.CLIENT.value,
                created_by=self._operated_by,
                updated_by=self._operated_by,
            )
            fake_password = ''.join([random.choice(string.ascii_letters + string.digits) for i in range(10)])
            dummy_password = 'rG%H7J+KSb' + fake_password
            user.set_password(dummy_password)
            try:
                user.save()
            except django.db.IntegrityError as e:
                code = e.args[0]
                if code == 1062:
                    logger.error(f"{e}: {traceback.format_exc()}")
                    raise self.UserDuplicateError("既にメールアドレスが登録されています")
                else:
                    raise e

    def is_valid(self):
        reader = csv.DictReader(io.StringIO(self._contents))
        if reader.fieldnames != self.filed_names:
            self.errors.append({
                'num': 1,
                'name': '',
                'message': "ヘッダ行が不正です",
            })
            return False

        mail_addresses = set()
        for index, row in enumerate(reader):
            if (mail_address := row['メールアドレス']) in mail_addresses:
                self.errors.append({
                    'num': index + 2,
                    'name': 'メールアドレス',
                    'message': "メールアドレスが重複しています",
                })
            mail_addresses.add(mail_address)

            serializer = UserClientCsvRowSerializer(data=self._convert_key(row))
            if not serializer.is_valid():
                for key, messages in serializer.errors.items():
                    for message in messages:
                        self.errors.append({
                            'num': index + 2,
                            'name': self.field_reverse_mapping[key],
                            'message': message,
                        })

            if mail_address:
                # 連絡先はemailとclient_idで一意になる必要があるため、login_nameは結合をする
                check_login_name = f"{mail_address}:{self._client.id}"
                if User.objects.filter(login_name=check_login_name).exists():
                    self.errors.append({
                        'num': index + 2,
                        'name': 'メールアドレス',
                        'message': "既に登録されているメールアドレスです。",
                    })

        self._validated = True
        return len(self.errors) == 0

    def _convert_key(self, row: dict):
        return {
            self.field_mapping[k]: v for k, v in row.items()
        }

    class NotValidatedError(Exception):
        pass

    class UserDuplicateError(Exception):
        pass


class UserCsvImporter:
    filed_names = [
        "メールアドレス",
        "パスワード",
        "名前",
        "部署名",
        "役職",
        "電話番号",
        "備考",
        '権限カテゴリID',
    ]

    field_mapping = {
        "メールアドレス": "login_name",
        "パスワード": "password",
        "名前": "username",
        "部署名": "division",
        "役職": "position",
        "電話番号": "tel",
        "備考": "memo",
        "権限カテゴリID": "permission_category_id"
    }

    field_reverse_mapping = {
        v: k for k, v in field_mapping.items()
    }

    def __init__(self, contents: str, operated_by: User):
        self._contents = contents
        self._operated_by = operated_by
        self._validated = False
        self.errors = []
        self.user_mailer = UserMailer()
        self.now = make_aware(datetime.datetime.now())

    def import_users(self):
        if not self._validated:
            raise self.NotValidatedError

        reader = csv.DictReader(io.StringIO(self._contents))
        for row in reader:
            email = row['メールアドレス']
            password = row['パスワード']
            permission_category_id = row['権限カテゴリID']
            values = {
                'account_id': self._operated_by.account.id,
                'client_id': None,
                'email': row['メールアドレス'],
                'username': row['名前'],
                'division': row['部署名'],
                'position': row['役職'],
                'tel': row['電話番号'],
                'memo': row['備考'],
                'type': User.Type.ACCOUNT.value,
                'created_by': self._operated_by,
                'updated_by': self._operated_by,
            }
            if password:
                values['password'] = make_password(password)
            user, created = User.objects.update_or_create(
                account_id=self._operated_by.account.id,
                login_name=email,
                defaults=values
            )
            if created:
                user_service = UserService()
                # 新規作成の場合のみ、OTP生成キーを作成する
                user_service.create_otp_secret(user)
                # 新規作成の場合のみ、初期の権限を付与する
                all_targets = [target.value for target in PermissionTarget.Target]
                # 権限が選択されていなかった場合は一般にする
                if not permission_category_id:
                    permission_category_id = 3  # 一般のIDが3のため
                # 不許可の権限を格納するリスト
                deny_targets = []
                is_allow_filter = Q(
                    permission_category_id=permission_category_id,
                    status=PermissionCategory.Status.ENABLE.value,
                    is_allow=False,
                    account_id=self._operated_by.account.id
                ) | Q(
                    permission_category_id=permission_category_id,
                    status=PermissionCategory.Status.ENABLE.value,
                    is_allow=False,
                    account_id=None
                )
                # PermissionCategoryのidに基づいて、is_allowがFalseのtarget_idをdeny_targetsに追加する
                permission_category = PermissionCategory.objects.filter(is_allow_filter).all()
                for permission in permission_category:
                    deny_targets.append(permission.target_id)
                # ライトプランではワークフローが使えない（したがって連絡先も不要になる）
                if self._operated_by.account.plan == Account.Plan.LIGHT:
                    deny_targets.extend(
                        [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                         PermissionTarget.Target.DISP_CLIENT_SETTING.value]
                    )

                allow_targets = list(set(all_targets) ^ set(deny_targets))
                user_service.create_user_permissions(user, self._operated_by, self.now, allow_targets, deny_targets)
                # Userのpermission_category_idを書き換える
                user.permission_category_id = permission_category_id
                user.save()
                # 新規作成時のメールの送信
                self.user_mailer.send_user_create_mail(user)
            else:
                if permission_category_id:
                    permission_all = []
                    wheres_base = {
                        'user_id': user.id,
                        'status': Statusable.Status.ENABLE.value,
                        'target__status': Statusable.Status.ENABLE.value
                    }
                    permission_base = Permission.objects.select_related('target').filter(**wheres_base)
                    try:
                        permission_category = PermissionCategory.objects.filter(permission_category_id=permission_category_id)
                        for param_permission in permission_category:
                            target_id = param_permission.target.id
                            wheres = {
                                'target_id': target_id
                            }
                            try:
                                permission = permission_base.filter(**wheres).first()
                            except Permission.DoesNotExist as e:
                                logger.info(f"{e}: {traceback.format_exc()}")
                                return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)
                            permission.is_allow = param_permission.is_allow
                            if self._operated_by.account.plan == Account.Plan.LIGHT.value:
                                if target_id in [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                                                 PermissionTarget.Target.DISP_CLIENT_SETTING.value]:
                                    permission.is_allow = False
                            permission.updated_by = self._operated_by
                            permission.updated_at = self.now
                            permission_all.append(permission)
                        Permission.objects.bulk_update(permission_all, fields=['is_allow', 'updated_by', 'updated_at'])
                        # Userのpermission_category_idを書き換える
                        user.permission_category_id = permission_category_id
                        user.save()
                    except DatabaseError as e:
                        logger.error(f"{e}: {traceback.format_exc()}")
                        return Response({"msg": ["権限の付与に失敗した可能性があります。"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                # 更新時のメールの送信
                self.user_mailer.send_user_modify_mail(user, self._operated_by)

    def is_valid(self):
        reader = csv.DictReader(io.StringIO(self._contents))
        if reader.fieldnames != self.filed_names:
            self.errors.append({
                'num': 1,
                'name': '',
                'message': "ヘッダ行が不正です",
            })
            return False

        mail_addresses = set()
        # メールアドレスのバリデーションチェックを入れる
        # 重複エラーは新規または更新のため、必要なし
        input_names = []
        for index, row in enumerate(reader):
            mail_address = row['メールアドレス']
            user_name = row['名前']
            permission_category_id = row['権限カテゴリID']
            try:
                validate_email(mail_address)
            except ValidationError:
                self.errors.append({
                    'num': index + 2,
                    'name': 'メールアドレス',
                    'message': "無効なメールアドレスが入力されています",
                })
                continue
            mail_addresses.add(mail_address)

            serializer = UserCsvRowSerializer(data=self._convert_key(row))
            if not serializer.is_valid():
                for key, messages in serializer.errors.items():
                    for message in messages:
                        self.errors.append({
                            'num': index + 2,
                            'name': self.field_reverse_mapping[key],
                            'message': message,
                        })

            # filterでemailだけ絞り込む、中身があればaccount_idを確認して、一致していれば更新、一致してなければエラー
            # login_nameでユニーク制約がかかっているため、filter結果は0件か1件のどちらか
            filter_user = User.objects.filter(login_name=mail_address).first()
            if filter_user:
                # アカウント内のユーザーの場合は更新するため、エラーにはしない
                # アカウント外のユーザーの場合は重複登録はできないためエラーにする
                if filter_user.account_id != self._operated_by.account.id:
                    self.errors.append({
                        'num': index + 2,
                        'name': 'メールアドレス',
                        'message': "既に登録されているメールアドレスです。",
                    })
            # 名前の重複エラーの実装
            check_account = {
                'account_id': self._operated_by.account.id,
                'status': User.Status.ENABLE.value,
                'type': User.Type.ACCOUNT.value,
                'is_bpo': False,
            }
            persons = User.objects.filter(**check_account).exclude(login_name=mail_address).all()
            cleaned_names = [person.username.replace(' ', '').replace('　', '').replace('\t', '') for person in persons]
            cleaned_username = user_name.replace(' ', '').replace('　', '').replace('\t', '')
            if cleaned_username in cleaned_names:
                self.errors.append({
                    'num': index + 2,
                    'name': '名前',
                    'message': "名前が重複しています。",
                })
            elif cleaned_username in input_names:
                self.errors.append({
                    'num': index + 2,
                    'name': '名前',
                    'message': "CSV内で名前が重複しています。",
                })
            else:
                input_names.append(cleaned_username)

            # 権限カテゴリのエラーの実装
            if permission_category_id:
                check_permission_id = Q(
                    id=permission_category_id,
                    status=PermissionCategoryKey.Status.ENABLE.value,
                    account_id=self._operated_by.account.id
                ) | Q(
                    id=permission_category_id,
                    status=PermissionCategoryKey.Status.ENABLE.value,
                    account_id=None
                )
                category_check = PermissionCategoryKey.objects.filter(check_permission_id).all()
                if not category_check:
                    self.errors.append({
                        'num': index + 2,
                        'name': '権限カテゴリID',
                        'message': "無効なカテゴリIDです。",
                    })

        self._validated = True
        return len(self.errors) == 0

    def _convert_key(self, row: dict):
        return {
            self.field_mapping[k]: v for k, v in row.items()
        }

    class NotValidatedError(Exception):
        pass

    class UserDuplicateError(Exception):
        pass


class UserClientCsvRowSerializer(serializers.Serializer):
    login_name = serializers.CharField(required=True, allow_blank=False, max_length=255)
    password = serializers.CharField(allow_blank=False, required=False)
    username = serializers.CharField(required=True, allow_blank=False, max_length=255)
    division = serializers.CharField(allow_blank=True, required=False, max_length=255)
    position = serializers.CharField(allow_blank=True, required=False, max_length=255)
    tel = serializers.CharField(allow_blank=True, required=False, max_length=255)
    memo = serializers.CharField(allow_blank=True, required=False, max_length=255)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_password(self, value):
        user = User()
        user.login_name = self.initial_data.get('login_name')
        user.username = self.initial_data.get('username')
        user.division = self.initial_data.get('division')
        user.position = self.initial_data.get('position')
        user.tel = self.initial_data.get('tel')
        user.memo = self.initial_data.get('memo')
        password_validation.validate_password(value, user)
        return value


class UserCsvRowSerializer(serializers.Serializer):
    login_name = serializers.CharField(required=True, allow_blank=False, max_length=255)
    password = serializers.CharField(allow_blank=True, required=False)
    username = serializers.CharField(required=True, allow_blank=False, max_length=255)
    division = serializers.CharField(allow_blank=True, required=False, max_length=255)
    position = serializers.CharField(allow_blank=True, required=False, max_length=255)
    tel = serializers.CharField(allow_blank=True, required=False, max_length=255)
    memo = serializers.CharField(allow_blank=True, required=False, max_length=255)
    permission_category_id = serializers.CharField(allow_blank=True, required=False, max_length=255)

    def update(self, instance, validated_data):
        pass

    def create(self, validated_data):
        pass

    def validate_password(self, value):
        user = User()
        user.login_name = self.initial_data.get('login_name')
        user.username = self.initial_data.get('username')
        user.division = self.initial_data.get('division')
        user.position = self.initial_data.get('position')
        user.tel = self.initial_data.get('tel')
        user.memo = self.initial_data.get('memo')

        if User.objects.filter(login_name=user.login_name).count() > 0 and not value:
            return value

        password_validation.validate_password(value, user)
        return value
