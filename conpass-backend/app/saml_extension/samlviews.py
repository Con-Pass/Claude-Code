# saml_app/views.py
from datetime import datetime
from logging import getLogger

from django.conf import settings
from django.contrib.auth import logout, get_user_model
from django.core.validators import EmailValidator
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework_jwt.settings import api_settings

from common.auth.views import update_last_login
from conpass.models.login_failure import LoginFailure
from saml_extension.helpers import get_saml_config_for_account


logger = getLogger(__name__)


def init_saml_auth(request, org_id):
    saml_settings = get_saml_config_for_account(org_id)
    if saml_settings:
        req = {
            'https': 'on' if request.is_secure() else 'off',
            'http_host': request.get_host(),
            'server_port': '443' if request.is_secure() else '80',
            'script_name': request.path,
            'get_data': request.GET.copy(),
            'post_data': request.POST.copy(),
        }

        return OneLogin_Saml2_Auth(req, saml_settings)
    raise NotFound(detail="No SAML configuration found for organization")


def saml_metadata(request, org_id):
    auth = init_saml_auth(request, org_id)
    settings = auth.get_settings()
    metadata = settings.get_sp_metadata()
    errors = settings.validate_metadata(metadata)
    if errors:
        return HttpResponse("validation error: " + ', '.join(errors), status=500)
    return HttpResponse(content=metadata, content_type='text/xml')


def saml_login(request, org_id):
    auth = init_saml_auth(request, org_id)
    # Redirect user to IdP login
    return HttpResponseRedirect(auth.login())


@csrf_exempt
def saml_acs(request, org_id):
    auth = init_saml_auth(request, org_id)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        return HttpResponse("SAML response error: " + ', '.join(errors), status=500)
    if not auth.is_authenticated():
        return HttpResponse("User not authenticated", status=401)

    # Extract user info from assertion
    user_email = None
    name_id = auth.get_nameid()
    attributes = auth.get_attributes()
    logger.info(f"saml attribute: {attributes}")
    if 'email' in attributes:
        user_email = attributes['email'][0]
    else:
        user_email = name_id

    email_validator = EmailValidator()
    try:
        email_validator(user_email)
    except Exception as e:
        logger.info(e)
        return JsonResponse({"error_message": "不正なメールアドレス形式です。"}, status=status.HTTP_400_BAD_REQUEST)

    login_failure = LoginFailure.objects.filter(email=user_email).first()
    is_locked, lock_message = LoginFailure.check_lock_status(login_failure)
    if is_locked:
        return JsonResponse({'error_message': lock_message}, status=status.HTTP_400_BAD_REQUEST)
    if login_failure:
        login_failure.delete()

    # Authenticate user in Django
    User = get_user_model()
    user = User.objects.filter(login_name=user_email).first()
    if not user:
        return HttpResponse("User not found", status=404)

    jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
    jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

    payload = jwt_payload_handler(user)
    token = jwt_encode_handler(payload)
    expiration = (datetime.utcnow() + api_settings.JWT_EXPIRATION_DELTA)
    response = redirect(settings.SSO_SAML_REDIRECTION_ENDPOINT)
    response.set_cookie(
        key=api_settings.JWT_AUTH_COOKIE,
        value=token,
        httponly=True,
        samesite='Strict',
        expires=expiration
    )
    response.set_cookie(
        "loggedIn",
        "1",
        samesite='Strict'
    )
    update_last_login(user)

    return response



def saml_logout(request, org_id):
    auth = init_saml_auth(request, org_id)
    name_id = request.session.get('samlNameId', None)
    session_index = request.session.get('samlSessionIndex', None)

    # Clear local session
    logout(request)

    # Send logout request to IdP
    return HttpResponseRedirect(auth.logout(name_id=name_id, session_index=session_index))


@csrf_exempt
def saml_sls(request, org_id):
    auth = init_saml_auth(request, org_id)
    url = auth.process_slo()
    errors = auth.get_errors()
    logout(request)  # Clear local session after logout response

    if errors:
        return HttpResponse("SAML logout error: " + ', '.join(errors), status=500)

    if url:
        return HttpResponseRedirect(url)
    else:
        return HttpResponseRedirect('/')
