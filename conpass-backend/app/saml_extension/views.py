import logging
import json
import traceback
import datetime
import base64
import xmltodict
import random
import string
from django.conf import settings
from django.contrib import auth
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseServerError
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from onelogin.saml2.utils import OneLogin_Saml2_Utils
from onelogin.saml2.settings import OneLogin_Saml2_Settings
from conpass.models import User, Account, SsoLogin, PermissionTarget, PermissionCategory
from conpass.services.user.user_service import UserService
from django.contrib.auth.hashers import make_password
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError
from rest_framework_jwt.settings import api_settings

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
jwt_decode_handler = api_settings.JWT_DECODE_HANDLER
jwt_get_username_from_payload = api_settings.JWT_PAYLOAD_GET_USERNAME_HANDLER

logger = logging.getLogger('saml_extension')


def prepare_django_request(request):
    """Extract data from a Django request in the way that OneLogin expects."""
    result = {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.META['HTTP_HOST'],
        'script_name': request.META['PATH_INFO'],
        'server_port': request.META['SERVER_PORT'],
        'get_data': request.GET.copy(),
        'post_data': request.POST.copy()
    }
    if settings.SAML_DESTINATION_HOST is not None:
        result['http_host'] = settings.SAML_DESTINATION_HOST
    if settings.SAML_DESTINATION_HTTPS is not None:
        result['https'] = settings.SAML_DESTINATION_HTTPS
        result['server_port'] = '443' if result['https'] else '80'
    if settings.SAML_DESTINATION_PORT is not None:
        result['server_port'] = settings.SAML_DESTINATION_PORT
    return result


@never_cache
def login(request):
    """Kick off a SAML login request."""

    if "orgid" in request.GET:
        orgId = request.GET.get("orgid")
    else:
        return HttpResponse("Not Company", status=400)

    newSettings = updateIDPSetting(oldSetting=settings, orgId=orgId)

    req = prepare_django_request(request)
    saml_auth = OneLogin_Saml2_Auth(req, old_settings=newSettings.ONELOGIN_SAML_SETTINGS)
    if 'next' in request.GET:
        redirect_to = OneLogin_Saml2_Utils.get_self_url(req) + request.GET['next']
    else:
        redirect_to = OneLogin_Saml2_Utils.get_self_url(req) + '/dashboard'
    url = saml_auth.login(redirect_to)
    request.session['AuthNRequestID'] = saml_auth.get_last_request_id()

    # ACSでORGIDを取得するために一時保存する
    updateSsoLogin(authReqId=request.session['AuthNRequestID'], orgId=orgId)

    return HttpResponseRedirect(url)


@never_cache
def logout(request):
    """Kick off a SAML logout request."""
    req = prepare_django_request(request)
    saml_auth = OneLogin_Saml2_Auth(req, old_settings=settings.ONELOGIN_SAML_SETTINGS)
    name_id = request.session.get('samlNameId', None)
    session_index = request.session.get('samlSessionIndex', None)
    name_id_format = request.session.get('samlNameIdFormat', None)
    name_id_nq = request.session.get('samlNameIdNameQualifier', None)
    name_id_spnq = request.session.get('samlNameIdSPNameQualifier', None)
    auth.logout(request)
    url = saml_auth.logout(
        name_id=name_id, session_index=session_index, nq=name_id_nq, name_id_format=name_id_format, spnq=name_id_spnq,
        return_to=OneLogin_Saml2_Utils.get_self_url(req) + settings.SAML_LOGOUT_REDIRECT
    )
    request.session['LogoutRequestID'] = saml_auth.get_last_request_id()
    return HttpResponseRedirect(url)


@never_cache
def saml_sls(request):
    """Handle a LogoutResponse from the IdP."""
    if request.method != 'GET':
        return HttpResponse('Method not allowed.', status=405)
    req = prepare_django_request(request)
    saml_auth = OneLogin_Saml2_Auth(req, old_settings=settings.ONELOGIN_SAML_SETTINGS)
    request_id = request.session.get('LogoutRequestID', None)
    try:
        url = saml_auth.process_slo(request_id=request_id, delete_session_cb=lambda: request.session.flush())
        errors = saml_auth.get_errors()
        if len(errors) == 0:
            auth.logout(request)
            redirect_to = url or settings.SAML_LOGOUT_REDIRECT
            return HttpResponseRedirect(redirect_to)
        else:
            logger.exception(saml_auth.get_last_error_reason())
            return HttpResponse("Invalid request", status=400)
    except UnicodeDecodeError:
        # Happens when someone messes with the response in the URL.  No need to log an exception.
        return HttpResponse("Invalid request - Unable to decode response", status=400)
    except Exception as e:
        logger.exception(e)
        return HttpResponse("Invalid request", status=400)


@never_cache
@csrf_exempt
def saml_acs(request):
    """Handle an AuthenticationResponse from the IdP."""
    logger.setLevel(logging.DEBUG)
    if request.method != 'POST':
        return HttpResponse('不正なアクセスです。', status=405)

    request_id = ''
    try:
        request_id = request.session['AuthNRequestID']
        logger.info(f"AuthNRequestID: {request_id}")
    except KeyError:
        # request.sessionに'AuthNRequestID'が含まれいない場合は、SAMLレスポンスをパースして'InResponseTo'からIDを取得する
        # IdpがAzuerAD、GoogleWorkspaceの場合はここに入る
        req = prepare_django_request(request)
        encoded_saml_response = req['post_data'].get('SAMLResponse')
        saml_response = base64.b64decode(encoded_saml_response)
        parsed_saml_response = xmltodict.parse(saml_response)
        if 'samlp:Response' in parsed_saml_response:
            if '@InResponseTo' in parsed_saml_response['samlp:Response']:
                request_id = parsed_saml_response['samlp:Response']['@InResponseTo']
                logger.info(f"samlp:Response @InResponseTo: {request_id}")
        elif 'saml2p:Response' in parsed_saml_response:
            if '@InResponseTo' in parsed_saml_response['saml2p:Response']:
                request_id = parsed_saml_response['saml2p:Response']['@InResponseTo']
                logger.info(f"saml2p:Response @InResponseTo': {request_id}")

    logger.info(f"{request_id=}")
    try:
        if not request_id:
            return HttpResponse(content="RequestIDが存在しません。", status=400)
        ssoLogin = SsoLogin.objects.get(auth_request_id=request_id)
    except SsoLogin.DoesNotExist:
        return HttpResponse(content="IDP情報が不正です", status=400)

    newSettings = updateIDPSetting(oldSetting=settings, orgId=ssoLogin.org_id)

    # # ここからーーーー認証ダミー用　実際の処理を行う場合はコメントアウトすること
    # # ローカル環境で動かす場合は暫定的にコメントアウトを外して以下の2行を有効にすること
    # user = updateUserTest(ssoLogin.org_id)
    # return HttpResponseRedirect(f"http://localhost:8801/sso/redirect?reqid={request.session['AuthNRequestID']}&userid={user['id']}")
    # # ここまでーーーー認証ダミー用　実際の処理を行う場合はコメントアウトすること

    try:
        req = prepare_django_request(request)
        # GCP環境の場合、ロードバランサがプロキシしてACSポートをつけてしまうため、reqのFQDNからポート部分を削除する。
        # ローカル環境の場合は、Idpからアクセスしてくる時にポートも指定されているためポート削除の下記の処理はコメントアウトをする。
        # logger.info(f"[before]http_host: {req['http_host']} , server_port: {req['server_port']}")
        fqdn_parts = req["http_host"].split(':')
        req["http_host"] = fqdn_parts[0]
        # portが443(https)または80(http)以外の場合は強制的にserver_portがサフィックスとして付与されれてしまうため、443か80に置き換える。
        # ※server_portを空にするとコロンだけが追加されてしまうため、空にすることはできない。
        protocol = 'https' if OneLogin_Saml2_Utils.is_https(req) else 'http'
        req["server_port"] = '443' if protocol == 'https' else '80'
        # logger.info(f"[after]http_host: {req['http_host']} , server_port: {req['server_port']}")

        saml_auth = OneLogin_Saml2_Auth(req, old_settings=newSettings.ONELOGIN_SAML_SETTINGS)
        errors = saml_auth.get_errors()
        saml_auth.process_response(request_id=request_id)
        errors = saml_auth.get_errors()

        if not errors:
            request.session['samlNameId'] = saml_auth.get_nameid()
            logger.info(f"samlNameId: {request.session['samlNameId']}")
            request.session['samlNameIdFormat'] = saml_auth.get_nameid_format()
            logger.info(f"samlNameIdFormat: {request.session['samlNameIdFormat']}")
            request.session['samlNameIdNameQualifier'] = saml_auth.get_nameid_nq()
            logger.info(f"samlNameIdNameQualifier: {request.session['samlNameIdNameQualifier']}")
            request.session['samlNameIdSPNameQualifier'] = saml_auth.get_nameid_spnq()
            logger.info(f"samlNameIdSPNameQualifier: {request.session['samlNameIdSPNameQualifier']}")
            request.session['samlSessionIndex'] = saml_auth.get_session_index()
            logger.info(f"samlSessionIndex: {request.session['samlSessionIndex']}")
            compas_user = updateUser(saml_auth, ssoLogin.org_id)
            return HttpResponseRedirect(f"/sso/redirect?reqid={request_id}&userid={compas_user['user'].id}")
            # ローカル環境用
            # return HttpResponseRedirect(f"http://localhost:8801/sso/redirect?reqid={request.session['AuthNRequestID']}&userid={compas_user['user'].id}")
        logger.exception(saml_auth.get_last_error_reason())
        return HttpResponse(content="Invalid Response2", status=400)
    except PermissionDenied:
        raise
    except Exception as e:
        logger.error(f"Invalid Response: {e}")
        return HttpResponse(content="Invalid Response", status=400)


def getSsoLogin(authReqId):
    try:
        ssoLogin = SsoLogin.objects.get(auth_request_id=authReqId)
        return ssoLogin
    except SsoLogin.DoesNotExist:
        return None


def updateSsoLogin(authReqId, orgId):
    try:
        ssoLogin = SsoLogin.objects.get(auth_request_id=authReqId)
    except SsoLogin.DoesNotExist:
        ssoLogin = SsoLogin()

    ssoLogin.auth_request_id = authReqId
    ssoLogin.org_id = orgId
    ssoLogin.save()


def deleteSsoLogin(authReqId):
    try:
        ssoLogin = SsoLogin.objects.get(auth_request_id=authReqId)
    except SsoLogin.DoesNotExist:
        return
    ssoLogin.delete()


def updateUserTest(org_id):

    isCreateUser = False

    try:
        account = Account.objects.get(org_id=org_id, status=Account.Status.ENABLE.value)
    except Account.DoesNotExist as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        raise

    try:
        user = User.objects.get(login_name='dummy_user@example.com', status=User.Status.ENABLE.value)
    except User.DoesNotExist:
        isCreateUser = True
        user = User()

    datetime_now = make_aware(datetime.datetime.now())

    try:
        user.login_name = 'dummy_user@example.com'

        # ユーザを作成する場合。パスワードは必須だが、SSOの場合不要のため一時的にランダムな文字列を設定
        if isCreateUser:
            user.password = make_password(generate_random_password())

        user.username = 'dummy_user@example.com'
        user.division = "dummy_division"
        user.position = "dummy_position"
        user.email = 'dummy_user@example.com'
        user.tel = "08012341234"
        user.memo = "dummy_memo"
        user.status = 1
        user.account_id = account.id
        user.type = 1
        user.is_bpo = False  # 利用者側は false のみ
        # datetime_now = make_aware(datetime.datetime.now())
        if isCreateUser:
            user.created_by_id = "1"
            user.created_at = datetime_now
        user.updated_by_id = "1"
        user.updated_at = datetime_now
        user.save()

        update_last_login(user)

        payload = jwt_payload_handler(user)

        return {
            'token': jwt_encode_handler(payload),
            'user': user,
            'id': user.id
        }
    except DatabaseError as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        return {}


def updateUser(samlUser, org_id):
    isCreateUser = False

    try:
        account = Account.objects.get(org_id=org_id, status=Account.Status.ENABLE.value)
    except Account.DoesNotExist as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        raise

    try:
        attributes = samlUser.get_attributes()
        username = attributes['username'][0]  # usernameにはメールアドレスを指定してもらう
        logger.info(f"username = {username}")
    except KeyError as e:
        logger.error(f"KeyError {e}: {traceback.format_exc()}")
        raise

    try:
        user = User.objects.get(login_name=username, status=User.Status.ENABLE.value)
    except User.DoesNotExist:
        isCreateUser = True
        user = User()

    datetime_now = make_aware(datetime.datetime.now())

    try:
        with transaction.atomic():
            if isCreateUser:
                user.login_name = username
                user.username = username
                user.division = ""
                user.position = ""
                user.email = username
                user.tel = ""
                user.memo = ""
                user.status = User.Status.ENABLE.value
                user.account_id = account.id
                user.type = User.Type.ACCOUNT.value  # 顧客アカウント
                user.is_bpo = False  # 利用者側は false のみ
                # user.updated_by_idには後(update_last_login)で更新ユーザーのIDをセットする
                user.updated_at = datetime_now
                # ユーザを作成する場合。パスワードは必須だが、SSOの場合不要のため一時的にランダムな文字列を設定
                user.password = make_password(generate_random_password())
                # user.created_by_idには後(update_last_login)で作成ユーザーのIDをセットする
                user.created_at = datetime_now

            user.save()

            update_last_login(user, isCreateUser)

            payload = jwt_payload_handler(user)

            return {
                'token': jwt_encode_handler(payload),
                'user': user,
            }
    except DatabaseError as e:
        logger.error(f"{e}: {traceback.format_exc()}")
        return {}


def update_last_login(user: User, isCreateUser: bool):
    now = make_aware(datetime.datetime.now())
    if isCreateUser:
        user.created_by_id = user.id
    user.updated_by_id = user.id
    user.last_login = now

    # ユーザーの新規作成時は権限設定を行う
    if isCreateUser:
        # 権限は一般（permission_category_id=3）とする
        permission_category_id = 3
        user_service = UserService()
        all_targets = [target.value for target in PermissionTarget.Target]

        # 不許可の権限を格納するリスト
        deny_targets = []
        wheres = {
            'permission_category_id': permission_category_id,
            'status': PermissionCategory.Status.ENABLE.value,
            'is_allow': False,
            'account_id': None
        }
        # PermissionCategoryのidに基づいて、is_allowがFalseのtarget_idをdeny_targetsに追加する
        permission_category = PermissionCategory.objects.filter(**wheres).all()
        for permission in permission_category:
            deny_targets.append(permission.target_id)

        # ライトプランではワークフローが使えない（したがって連絡先も不要になる）
        if user.account.plan == Account.Plan.LIGHT:
            deny_targets.extend(
                [PermissionTarget.Target.DISP_WORKFLOW_SETTING.value,
                    PermissionTarget.Target.DISP_CLIENT_SETTING.value]
            )
        allow_targets = list(set(all_targets) ^ set(deny_targets))
        user_service.create_user_permissions(user, user, now, allow_targets, deny_targets)

        # Userのpermission_category_idを書き換える
        user.permission_category_id = permission_category_id

    user.save()


def metadata(request):
    """Render the metadata of this service."""
    metadata_dict = settings.ONELOGIN_SAML_SETTINGS.get_sp_metadata()
    errors = settings.ONELOGIN_SAML_SETTINGS.validate_metadata(metadata_dict)

    if len(errors) == 0:
        resp = HttpResponse(content=metadata_dict, content_type='text/xml')
    else:
        resp = HttpResponseServerError(content=', '.join(errors))
    return resp


def updateIDPSetting(oldSetting, orgId):

    try:
        account = Account.objects.get(org_id=orgId)
    except Account.DoesNotExist as e:
        logger.info(e)
        return HttpResponse("アカウントが見つかりません", status=400)

    idp = json.loads(account.idp_settings) if account.idp_settings else {}

    if idp.get('idpEntityId') is None:
        return HttpResponse("EntityIdが設定されておりません", status=400)
    if idp.get('singleSignOnUrl') is None:
        return HttpResponse("singleSignOnUrlが設定されておりません", status=400)
    if idp.get('x509Certificate') is None:
        return HttpResponse("x509Certificateが設定されておりません", status=400)

    # 結局参照のコピーにしかならないので、あまり意味はない
    newSetting = oldSetting

    if idp.get('idpEntityId') is not None:
        newSetting.SAML_SETTINGS['idp']['entityId'] = idp['idpEntityId']
    if idp.get('singleSignOnUrl') is not None:
        newSetting.SAML_SETTINGS['idp']['singleSignOnService']['url'] = idp['singleSignOnUrl']
    if idp.get('x509Certificate') is not None:
        newSetting.SAML_SETTINGS['idp']['x509cert'] = idp['x509Certificate']

    newSetting.ONELOGIN_SAML_SETTINGS = OneLogin_Saml2_Settings(newSetting.SAML_SETTINGS, newSetting.SAML_BASE_DIRECTORY)
    return newSetting


def generate_random_password():
    characters = string.ascii_letters + string.digits  # 英字（大文字と小文字）と数字
    password = ''.join(random.choice(characters) for _ in range(128))  # ランダムな文字列を生成します
    return password
