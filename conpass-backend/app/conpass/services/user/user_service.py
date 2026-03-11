import traceback
import uuid
from datetime import datetime

from typing import List, Optional
import pyotp

from django.db import DatabaseError
from django.utils.timezone import make_aware

from conpass.models import User, PermissionTarget, Permission, SocialLogin, PermissionCategory
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.utils import jwt_response_payload_handler
from logging import getLogger
from conpass.models.constants import Statusable

logger = getLogger(__name__)


class UserService:

    def get_user_list(self, params):
        # query
        wheres = {
            'status': User.Status.ENABLE.value,
        }

        if params.get('userName'):
            wheres['username__contains'] = params.get('userName')
        wheres['type'] = params.get('userType')
        if params.get('userType') == User.Type.CLIENT.value:
            wheres['client__provider_account__id'] = params.get('account')
        else:
            wheres['account_id'] = params.get('account')
        if params.get('clientId'):
            wheres['client_id'] = params.get('clientId')
        wheres['is_bpo'] = not not params.get('isBpo')

        user_list = list(User.objects.select_related('corporate', 'client').filter(**wheres).all())
        return user_list

    def add_new_token_headler(self, response: Response, user: User, cookie_name=api_settings.JWT_AUTH_COOKIE):
        """
        新しいJWTを払い出してヘッダに付与する
        レスポンス自体はそれぞれで用意してください
        """
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)
        if api_settings.JWT_AUTH_COOKIE:
            expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
            response.set_cookie(cookie_name,
                                token,
                                expires=expiration,
                                httponly=True,
                                samesite='Strict')  # SameSiteを指定
        return response

    def create_user_permissions(self, user: User, login_user: User, now: datetime,
                                allow_target_ids: List[int],
                                deny_target_ids: List[int]) -> List[Permission]:
        # 指定のpermission_target で新しく権限を作る
        # 新規にユーザが作成された時を想定
        if len(allow_target_ids) + len(deny_target_ids) == 0:
            return []
        permission_list = []
        try:
            for target_id in set(allow_target_ids + deny_target_ids):
                new_permission = Permission()
                new_permission.id = None
                new_permission.user = user
                try:
                    # 無効になっている権限は無視
                    permission_target = PermissionTarget.objects.get(pk=target_id,
                                                                     status=Statusable.Status.ENABLE.value)
                except PermissionTarget.DoesNotExist as e:
                    logger.info(f"{e}: {traceback.format_exc()}")
                    continue
                new_permission.target = permission_target
                new_permission.is_allow = target_id in allow_target_ids and target_id not in deny_target_ids
                new_permission.status = Statusable.Status.ENABLE.value
                new_permission.created_at = now
                new_permission.created_by = login_user
                new_permission.updated_at = now
                new_permission.created_by = login_user
                permission_list.append(new_permission)
            Permission.objects.bulk_create(permission_list)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return permission_list

    def create_permission_category(self, user: User, login_user: User, now: datetime,
                                   allow_target_ids: List[int],
                                   deny_target_ids: List[int]) -> List[PermissionCategory]:
        # 指定のpermission_target で新しく権限を作る
        # 新規にユーザが作成された時を想定
        if len(allow_target_ids) + len(deny_target_ids) == 0:
            return []
        permission_list = []
        try:
            for target_id in set(allow_target_ids + deny_target_ids):
                new_permission = PermissionCategory()
                new_permission.id = None
                new_permission.user = user
                try:
                    # 無効になっている権限は無視
                    permission_target = PermissionTarget.objects.get(pk=target_id,
                                                                     status=Statusable.Status.ENABLE.value)
                except PermissionTarget.DoesNotExist as e:
                    logger.info(f"{e}: {traceback.format_exc()}")
                    continue
                new_permission.target = permission_target
                new_permission.is_allow = target_id in allow_target_ids and target_id not in deny_target_ids
                new_permission.status = Statusable.Status.ENABLE.value
                new_permission.created_at = now
                new_permission.created_by = login_user
                new_permission.updated_at = now
                new_permission.created_by = login_user
                permission_list.append(new_permission)
            PermissionCategory.objects.bulk_create(permission_list)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return permission_list

    def create_otp_secret(self, user: User):
        otp_secret = pyotp.random_base32()
        try:
            user.otp_secret = otp_secret
            user.save()
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return user

    def delete_user_data(self, delete_user: User, login_user: User, now: Optional[datetime], is_bulk=False):
        if not now:
            now = make_aware(datetime.now())
        try:
            delete_user.login_name = str(uuid.uuid4())
            delete_user.status = User.Status.DISABLE.value
            delete_user.updated_by = login_user
            delete_user.updated_at = now
            if not is_bulk:
                delete_user.save()
            self.delete_user_sociallogin(delete_user, login_user, now)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        return delete_user

    def bulk_delete_user_data(self, delete_users: User, login_user: User, now: Optional[datetime]):
        if not now:
            now = make_aware(datetime.now())
        deleted_social_logins = []
        try:
            for delete_user in delete_users:
                delete_user.login_name = str(uuid.uuid4())
                delete_user.status = User.Status.DISABLE.value
                delete_user.updated_by = login_user
                delete_user.updated_at = now
                if delete_social_logins := self.delete_user_sociallogin(delete_user, login_user, now, is_bulk=True):
                    deleted_social_logins + delete_social_logins
            User.objects.bulk_update(delete_users, fields=['login_name', 'status', 'updated_by', 'updated_at'])
            if len(deleted_social_logins) > 0:
                SocialLogin.objects.bulk_update(deleted_social_logins,
                                                fields=['access_token', 'status', 'refresh_token', 'firebase_uid',
                                                        'ms_photo_data', 'photo_url', 'provider_data_uid',
                                                        'updated_at', 'updated_by'])
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e

    def delete_user_sociallogin(self, delete_user: User, login_user: User, now: datetime, is_bulk=False):
        try:
            # 259 1ユーザに対して紐付け数分の登録があるため全て削除する(データは残しておかない)
            social_logins = SocialLogin.objects.filter(user_id=delete_user.id)
            for social_login in social_logins:
                if not is_bulk:
                    social_login.delete()
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            raise e
        except SocialLogin.DoesNotExist as e:
            # ない場合もある
            logger.info(e)
            return None
        return social_logins
