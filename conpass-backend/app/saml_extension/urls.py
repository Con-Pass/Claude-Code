from django.urls import re_path, path

from saml_extension import views, samlviews

app_name = 'saml_extension'

urlpatterns = [
    path('<str:org_id>/metadata/', samlviews.saml_metadata, name='saml_metadata'),
    path('<str:org_id>/login/', samlviews.saml_login, name='saml_login'),
    path('<str:org_id>/acs/', samlviews.saml_acs, name='saml_acs'),
    # path('<str:org_id>/logout/', samlviews.saml_logout, name='saml_logout'),
    # path('<str:org_id>/sls/', samlviews.saml_sls, name='saml_sls'),
]
