import re
import traceback
from logging import getLogger
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from conpass.views.mailtemplate.serializer.mail_template_list_serializer import MailTemplateListResponseBodySerializer
from conpass.views.mailtemplate.serializer.mail_tag_list_serializer import MailTagListResponseBodySerializer
from conpass.views.mailtemplate.serializer.mail_template_edit_serializer import MailTemplateEditResponseBodySerializer, \
    MailTemplateEditPostRequestBodySerializer, MailTemplateEditGetRequestBodySerializer
from conpass.views.mailtemplate.serializer.mail_template_preview_serializer\
    import MailTemplatePreviewRequestBodySerializer, MailTemplatePreviewResponseBodySerializer
from conpass.models import MailTemplate, MailTag
import datetime
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class MailTemplateListView(APIView):
    def get(self, request):
        account_id = self.request.user.account_id
        templates = []
        template_types = MailTemplate.Type
        for type in template_types:

            mail_template = MailTemplate.objects.filter(template_type=type.value,
                                                        status=MailTemplate.Status.ENABLE.value,
                                                        account_id=account_id).first()
            if not mail_template:
                mail_template = MailTemplate()
                mail_template.template_type = type.value

            templates.append(mail_template)

        res_serializer = MailTemplateListResponseBodySerializer(templates)
        return Response(data=res_serializer.data)


class MailTagListView(APIView):
    """
    メールテンプレート設定画面のタグ一覧
    """
    def get(self, request):

        tags = MailTag.objects.filter(status=MailTag.Status.ENABLE.value).all()

        res_serializer = MailTagListResponseBodySerializer(tags)
        return Response(data=res_serializer.data)


class MailTemplateEditView(APIView):
    def get(self, request):
        """
        メールテンプレート設定画面初期表示
        """
        req_serializer = MailTemplateEditGetRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        account_id = self.request.user.account_id
        template_data = {}

        if req_serializer.data.get('id'):
            try:
                template_data = MailTemplate.objects.filter(pk=req_serializer.data.get('id'),
                                                            account_id=account_id).get()
            except MailTemplate.DoesNotExist as e:
                logger.info(e)
                return Response('テンプレートがありません', status=status.HTTP_400_BAD_REQUEST)

        else:
            template_data['template_type'] = req_serializer.data.get('type')

        res_serializer = MailTemplateEditResponseBodySerializer(template_data)
        return Response(data=res_serializer.data)

    def post(self, request):
        """
        メールテンプレート設定画面登録処理
        """
        req_serializer = MailTemplateEditPostRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = self.request.user.id
        account_id = self.request.user.account_id
        is_nest_list = [MailTemplate.Type.MAIL_HEADER.value, MailTemplate.Type.MAIL_FOOTER.value]

        # タグの入力チェック
        tags = list(MailTag.objects.filter(status=MailTag.Status.ENABLE.value).values_list('tag', flat=True))
        check_texts = re.findall(r'\{.*?\}', req_serializer.data.get('templateText'))
        for txt in check_texts:
            # タグが間違っていないかチェック
            if txt not in tags:
                return Response({"msg": ["使用できないタグが含まれています：{0}".format(txt)]},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            # ヘッダ・フッタでは{header},{footer}を使用させない
            if int(req_serializer.data.get('templateType')) in is_nest_list:
                if txt in [MailTag.MailTagConst.HEADER.value, MailTag.MailTagConst.FOOTER.value]:
                    return Response({"msg": ["使用できないタグが含まれています：{0}".format(txt)]},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            if req_serializer.data.get('id'):
                mail_template = MailTemplate.objects.filter(pk=req_serializer.data.get('id'),
                                                            account_id=account_id).first()
                mail_template.template_text = req_serializer.data.get('templateText')
                mail_template.updated_by_id = user_id
                mail_template.updated_at = make_aware(datetime.datetime.now())
            else:
                mail_template = MailTemplate()
                mail_template.template_type = req_serializer.data.get('templateType')
                mail_template.template_text = req_serializer.data.get('templateText')
                mail_template.account_id = account_id
                mail_template.is_nest_available = True\
                    if int(req_serializer.data.get('templateType')) in is_nest_list else False

                mail_template.created_by_id = user_id
                mail_template.created_at = make_aware(datetime.datetime.now())
                mail_template.updated_by_id = user_id
                mail_template.updated_at = make_aware(datetime.datetime.now())
            mail_template.save()

        except MailTemplate.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["更新するテンプレートがありません"]}, status=status.HTTP_400_BAD_REQUEST)
        except DatabaseError as e:
            logger.error(f"{e}: {traceback.format_exc()}")
            return Response({"msg": ["DBエラーが発生しました"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=status.HTTP_200_OK)


class MailTemplatePreviewView(APIView):
    """
    プレビューの表示内容を返す
    """
    def get(self, request):
        req_serializer = MailTemplatePreviewRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        params = req_serializer.data
        preview = {}
        account_id = self.request.user.account_id
        result_text = params.get('body')

        # ダミーデータに置換
        header = MailTemplate.objects.filter(template_type=MailTemplate.Type.MAIL_HEADER.value,
                                             account_id=account_id).first()
        header_text = header.template_text if header else ""
        footer = MailTemplate.objects.filter(template_type=MailTemplate.Type.MAIL_FOOTER.value,
                                             account_id=account_id).first()
        footer_text = footer.template_text if footer else ""

        result_text = result_text.replace(MailTag.MailTagConst.HEADER.value, header_text if header_text else "")
        result_text = result_text.replace(MailTag.MailTagConst.FOOTER.value, footer_text if footer_text else "")
        result_text = result_text.replace(MailTag.MailTagConst.CLIENT.value,
                                          params.get('client') if params.get('client') else "")
        result_text = result_text.replace(MailTag.MailTagConst.CONCLUDE_DATE.value,
                                          params.get('concludeDate') if params.get('concludeDate') else "")
        result_text = result_text.replace(MailTag.MailTagConst.LIMIT_DATE.value,
                                          params.get('limitDate') if params.get('limitDate') else "")
        result_text = result_text.replace(MailTag.MailTagConst.DETAIL_URL.value,
                                          params.get('detailUrl') if params.get('detailUrl') else "")
        result_text = result_text.replace(MailTag.MailTagConst.RENEW_URL.value,
                                          params.get('renewUrl') if params.get('renewUrl') else "")
        preview['body'] = result_text

        res_serializer = MailTemplatePreviewResponseBodySerializer(preview)
        return Response(data=res_serializer.data)
