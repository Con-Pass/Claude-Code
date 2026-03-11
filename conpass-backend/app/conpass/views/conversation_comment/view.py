from logging import getLogger
import datetime

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.constants import Statusable
from conpass.views.conversation_comment.serializer.conversation_comment_serializer import \
    CommentDeleteRequestBodySerializer
from conpass.views.conversation_comment.serializer.conversation_comment_edit_serializer import CommentEditRequestBodySerializer
from conpass.models import ConversationComment
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class CommentEditView(APIView):

    def post(self, request):
        """
        コメントを編集する
        """
        req_serializer = CommentEditRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        edit_comment_id = req_serializer.data.get('id')
        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())
        conversation_id = req_serializer.data.get('conversationId')
        edit_comment = req_serializer.data.get('comment')
        contract_id = req_serializer.data.get('contractId')

        wheres = {
            'pk': edit_comment_id,
            'contract_id': contract_id,
            'user_id': user_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if edit_comment_id:
            try:
                edit_conversation_comment = ConversationComment.objects.get(**wheres)
            except ConversationComment.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)
        else:
            edit_conversation_comment = ConversationComment()

        try:
            edit_conversation_comment.conversation_id = conversation_id
            edit_conversation_comment.user_id = user_id
            edit_conversation_comment.contract_id = contract_id
            edit_conversation_comment.status = Statusable.Status.ENABLE.value
            edit_conversation_comment.comment = edit_comment
            edit_conversation_comment.updated_by_id = user_id
            edit_conversation_comment.updated_at = now
            edit_conversation_comment.save()
        except DatabaseError as e:
            logger.info(e)
            return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)

        response = Response({'comment_uid': str(edit_conversation_comment.id)}, status=status.HTTP_200_OK)

        return response


class CommentDeleteView(APIView):

    def post(self, request):
        """
        コメントを削除する
        """
        req_serializer = CommentDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delete_comment_id = req_serializer.data.get('id')
        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())

        wheres = {
            'pk': delete_comment_id,
            'user_id': user_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if delete_comment_id:
            try:
                delete_comment = ConversationComment.objects.get(**wheres)
                delete_comment.status = Statusable.Status.DISABLE.value
                delete_comment.updated_by_id = user_id
                delete_comment.updated_at = now
                delete_comment.save()
            except ConversationComment.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)
            except DatabaseError as e:
                print(e)
                return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response("Success", status=status.HTTP_200_OK)
