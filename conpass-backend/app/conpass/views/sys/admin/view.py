import uuid
from logging import getLogger

from djangorestframework_camel_case.render import CamelCaseJSONRenderer
from rest_framework import status
from rest_framework.renderers import BrowsableAPIRenderer
from rest_framework.response import Response

from conpass.models import User
from conpass.services.paginate.paginate import StandardResultsSetPagination
from conpass.services.user.user_service import UserService
from conpass.views.sys.admin.serializer.sys_admin_delete_serializer import SysAdminDeleteRequestSerializer
from conpass.views.sys.admin.serializer.sys_admin_detail_serializer import SysAdminDetailRequestSerializer
from conpass.views.sys.admin.serializer.sys_admin_edit_serializer import SysAdminEditRequestSerializer, \
    SysAdminNewRequestSerializer
from conpass.views.sys.admin.serializer.sys_admin_list_serializer import SysAdminListRequestSerializer
from conpass.views.sys.admin.serializer.sys_admin_serializer import SysAdminSerializer
from conpass.views.sys.common import SysAPIView, SysListAPIView

logger = getLogger(__name__)


class SysAdminListView(SysListAPIView):
    serializer_class = SysAdminSerializer
    pagination_class = StandardResultsSetPagination
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def get_queryset(self):
        req_serializer = SysAdminListRequestSerializer(data=self.request.query_params)
        req_serializer.is_valid(raise_exception=True)

        queryset = User.objects.filter(
            type=User.Type.ADMIN.value,
            status=User.Status.ENABLE.value,
        )
        if user_name := req_serializer.data.get('userName'):
            queryset = queryset.filter(username__contains=user_name)
        return queryset


class SysAdminDeleteView(SysAPIView):
    def delete(self, request):
        req_serializer = SysAdminDeleteRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        result_list = []
        for delete_id in req_serializer.data.get('ids'):
            try:
                delete_user = User.objects.get(
                    id=delete_id,
                    type=User.Type.ADMIN.value,
                )
            except User.DoesNotExist as e:
                logger.info(e)
                return Response({'msg': 'パラメータが不正です'}, status=status.HTTP_400_BAD_REQUEST)

            user_service = UserService()
            user_service.delete_user_data(delete_user, self.request.user, None)
            result_list.append(delete_id)

        return Response({'success': True})


class SysAdminDetailView(SysAPIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def get(self, request):
        req_serializer = SysAdminDetailRequestSerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            admin = User.objects.get(pk=req_serializer.data.get('id'))
        except User.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        res_serializer = SysAdminSerializer(admin)
        return Response(data=res_serializer.data)


class SysAdminNewView(SysAPIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def post(self, request):
        req_serializer = SysAdminNewRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = req_serializer.validated_data
        admin = User(
            login_name=validated_data['loginName'],
            email=validated_data['email'],
            username=validated_data['username'],
            type=User.Type.ADMIN.value,
            status=User.Status.ENABLE.value,
            created_by=self.request.user,
            updated_by=self.request.user,
        )
        admin.set_password(validated_data['password'])
        admin.save()

        res_serializer = SysAdminSerializer(admin)
        return Response(data=res_serializer.data, status=status.HTTP_200_OK)


class SysAdminEditView(SysAPIView):
    renderer_classes = [
        CamelCaseJSONRenderer,
        BrowsableAPIRenderer,
    ]

    def post(self, request):
        req_serializer = SysAdminEditRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        validated_data = req_serializer.validated_data

        try:
            admin = User.objects.get(
                pk=req_serializer.data.get('id'),
                type=User.Type.ADMIN.value,
                status=User.Status.ENABLE.value,
            )
        except User.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["パラメータが不正です"]}, status=status.HTTP_400_BAD_REQUEST)

        admin.login_name = validated_data['loginName'] or admin.login_name
        admin.username = validated_data['username'] or admin.username
        admin.email = validated_data['email'] or admin.email
        if validated_data['password']:
            admin.set_password(validated_data['password'])
        admin.updated_by = self.request.user
        admin.save()

        res_serializer = SysAdminSerializer(admin)
        return Response(data=res_serializer.data, status=status.HTTP_200_OK)
