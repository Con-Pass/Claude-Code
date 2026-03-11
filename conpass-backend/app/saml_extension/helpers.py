import json
import os
from conpass.models import Account
from onelogin.saml2.auth import OneLogin_Saml2_Auth
from django.conf import settings



def get_saml_config_for_account(org_id):
    base_url = f"{settings.SSO_SAML_BASE_URL}/{org_id}"
    account_config= Account.objects.filter(org_id=org_id).first()
    if not account_config:
        return None

    account_idp_settings= account_config.idp_settings
    if not account_idp_settings:
        return None

    idp=json.loads(account_idp_settings)
    return{
        "strict": True,
        "debug": True,
        "sp": {
            "entityId": f"{base_url}/metadata/",
            "assertionConsumerService": {
                "url": f"{base_url}/acs/",
                "binding": f"{settings.SSO_SAML_SP_ACS_BINDING}",
            },
            "singleLogoutService": {
                "url": f"{base_url}/sls/",
                "binding": f"{settings.SSO_SAML_SP_SLS_BINDING}",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": "",
            "privateKey": "",
        },
        "security":{
            'wantMessagesSigned': True,
            'wantAssertionsSigned': False,
            'signatureAlgorithm': 'rsa-sha256',
            'digestAlgorithm': 'sha256',
        },
        "idp":{
            "entityId": idp["idpEntityId"],
            "singleSignOnService": {
                "url": idp["singleSignOnUrl"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "singleLogoutService": {
                "url": os.environ.get('SSO_SAML_SP_SLS_URL', 'http://localhost:8801/saml2/acs/'),
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
            },
            "x509cert": idp["x509Certificate"]
        }
    }





def init_saml_auth(request, org_id):
    saml_settings = get_saml_config_for_account(org_id)

    req = {
        'https': 'on' if request.is_secure() else 'off',
        'http_host': request.get_host(),
        'server_port': request.META['SERVER_PORT'],
        'script_name': request.path,
        'get_data': request.GET.copy(),
        'post_data': request.POST.copy(),
    }

    return OneLogin_Saml2_Auth(req, saml_settings)
