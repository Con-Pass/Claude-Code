import base64
import traceback
import urllib
import zipfile
from logging import getLogger
import datetime
import os
import subprocess
import tempfile
import requests
from requests.exceptions import Timeout

from bs4 import BeautifulSoup, NavigableString, Tag
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from conpass.models.constants import Statusable
from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName
from conpass.views.conversation.serializer.conversation_serializer import ConversationDeleteRequestBodySerializer, \
    ConversationResponseBodySerializer, ConversationRequestBodySerializer, ConversationDeleteAllRequestBodySerializer, \
    ConversationFetchRequestBodySerializer
from conpass.views.conversation.serializer.conversation_edit_serializer import ConversationCreateResponseBodySerializer
from conpass.views.conversation.serializer.conversation_upload_serializer import UploadWordFileRequestSerializer
from conpass.models import Conversation, ConversationComment, ContractBody, Contract, File
from django.utils.timezone import make_aware
from django.db.utils import DatabaseError

logger = getLogger(__name__)


class ConversationListView(APIView):

    def get(self, request):
        """
        契約書に紐づくコメントを全件取得する
        """
        req_serializer = ConversationRequestBodySerializer(data=request.query_params)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        contract_id = req_serializer.data.get('contract_id')
        conversation_id = req_serializer.data.get('conversation_id')

        wheres = {
            'id': conversation_id,
            'contract_id': contract_id,
            'status': Statusable.Status.ENABLE.value,
        }
        comment_wheres = {
            'conversation_id': conversation_id,
            'contract_id': contract_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if contract_id:
            try:
                conversation = Conversation.objects.get(**wheres)
                comments = ConversationComment.objects.filter(**comment_wheres).all()
            except Conversation.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。"]}, status=status.HTTP_400_BAD_REQUEST)
            # Conversationに紐づくコメントを取得
            conversation.comments = []
            for comment in comments:
                if conversation.id == comment.conversation_id:
                    if comment.author is None:
                        comment.author = comment.user.username
                    conversation.comments.append(comment)
        else:
            conversation = Conversation()

        res_serializer = ConversationResponseBodySerializer(conversation)
        return Response(res_serializer.data, status=status.HTTP_200_OK)


class ConversationCreateView(APIView):

    def post(self, request):
        """
        契約書に紐づくコメントスレッドを作成する
        """
        req_serializer = ConversationCreateResponseBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())
        contract_id = req_serializer.data.get('contractId')
        comment = req_serializer.data.get('comment')

        if contract_id:
            try:
                # Conversationを作成
                conversation = Conversation()
                conversation.contract_id = contract_id
                conversation.user_id = user_id
                conversation.status = Statusable.Status.ENABLE.value
                conversation.created_by_id = user_id
                conversation.created_at = now
                conversation.updated_by_id = user_id
                conversation.updated_at = now
                conversation.save()
                # ConversationCommentを作成
                conversation_comment = ConversationComment()
                conversation_comment.conversation_id = conversation.id
                conversation_comment.contract_id = contract_id
                conversation_comment.comment = comment
                conversation_comment.user_id = user_id
                conversation_comment.status = Statusable.Status.ENABLE.value
                conversation_comment.created_by_id = user_id
                conversation_comment.created_at = now
                conversation_comment.updated_by_id = user_id
                conversation_comment.updated_at = now
                conversation_comment.save()
            except DatabaseError as e:
                logger.info(e)
                return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)

        response = Response({'conversation_uid': str(conversation.id)}, status=status.HTTP_200_OK)

        return response


class ConversationDeleteView(APIView):

    def post(self, request):
        """
        スレッドを削除する
        """
        req_serializer = ConversationDeleteRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delete_conversation_id = req_serializer.data.get('id')
        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())

        wheres = {
            'pk': delete_conversation_id,
            'user_id': user_id,
            'status': Statusable.Status.ENABLE.value,
        }
        comment_wheres = {
            'conversation_id': delete_conversation_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if delete_conversation_id:
            try:
                delete_conversation = Conversation.objects.get(**wheres)
                delete_conversation.status = Statusable.Status.DISABLE.value
                delete_conversation.updated_by_id = user_id
                delete_conversation.updated_at = now
                delete_conversation.save()
                delete_comments = ConversationComment.objects.filter(**comment_wheres).all()
                if delete_comments:
                    for delete_comment in delete_comments:
                        try:
                            delete_comment.status = Statusable.Status.DISABLE.value
                            delete_comment.updated_by_id = user_id
                            delete_comment.updated_at = now
                            delete_comment.save()
                        except DatabaseError as e:
                            logger.error(f"{e}: {traceback.format_exc()}")
                            continue
            except Conversation.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。1"]}, status=status.HTTP_400_BAD_REQUEST)
            except DatabaseError as e:
                print(e)
                return Response({"msg": ["DBエラーが発生しました。2"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response("Success", status=status.HTTP_200_OK)


class ConversationDeleteAllView(APIView):

    def post(self, request):
        """
        スレッドを全部削除する
        """
        req_serializer = ConversationDeleteAllRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delete_contract_id = req_serializer.data.get('contract_id')
        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())

        wheres = {
            'contract_id': delete_contract_id,
            'status': Statusable.Status.ENABLE.value,
        }
        if delete_contract_id:
            try:
                delete_conversations = Conversation.objects.filter(**wheres).all()
                if delete_conversations:
                    for delete_conversation in delete_conversations:
                        comment_wheres = {
                            'conversation_id': delete_conversation.id,
                            'contract_id': delete_contract_id,
                            'status': Statusable.Status.ENABLE.value,
                        }
                        try:
                            delete_conversation.status = Statusable.Status.DISABLE.value
                            delete_conversation.updated_by_id = user_id
                            delete_conversation.updated_at = now
                            delete_conversation.save()
                            delete_comments = ConversationComment.objects.filter(**comment_wheres).all()
                            if delete_comments:
                                for delete_comment in delete_comments:
                                    try:
                                        delete_comment.status = Statusable.Status.DISABLE.value
                                        delete_comment.updated_by_id = user_id
                                        delete_comment.updated_at = now
                                        delete_comment.save()
                                    except DatabaseError as e:
                                        logger.error(f"{e}: {traceback.format_exc()}")
                                        continue
                        except DatabaseError as e:
                            logger.error(f"{e}: {traceback.format_exc()}")
                            continue
                response = Response("Success", status=status.HTTP_200_OK)
            except Conversation.DoesNotExist as e:
                logger.info(e)
                return Response({"msg": ["パラメータが不正です。1"]}, status=status.HTTP_400_BAD_REQUEST)

        return response


class ConversationFetchView(APIView):

    def post(self, request):
        """
        WordをペーストしたBodyからコメントを取得する
        """
        req_serializer = ConversationFetchRequestBodySerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        body = req_serializer.data.get('body')
        fetch_contract_id = req_serializer.data.get('contract_id')
        user_id = self.request.user.id
        now = make_aware(datetime.datetime.now())

        # デコード処理
        decoded_body = urllib.parse.unquote(body)
        decoded_body = base64.b64decode(decoded_body).decode('utf-8')
        decoded_body = urllib.parse.unquote(decoded_body)

        soup = BeautifulSoup(decoded_body, 'html.parser')

        hr_data_dict = {}

        # class="msocomoff"を持つhrタグの親要素を取得
        hr_element = soup.find('hr', {'class': 'msocomoff'})
        if hr_element is None:
            return Response({'msg': '抽出対象のコメントはございません。'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            parent_div = hr_element.find_parent('div')

            if parent_div is None:
                return Response({'msg': '文章内に抽出対象のコメントを確認できませんでした。'},
                                status=status.HTTP_400_BAD_REQUEST)

            # div内のpタグをすべて取得
            p_elements = parent_div.find_all('p')

            for p_element in p_elements:
                # aタグからナンバリングを取得
                a_element = p_element.find('a', {'class': 'msocomoff'})
                # aタグがない場合は次のpタグへ
                if a_element is None:
                    continue
                href_value = a_element.get('href')
                commentUid = href_value.split('_').pop()

                first_span = p_element.find('span', {'class': 'MsoCommentReference'})
                first_span.extract()

                # コメントを取得
                hr_text = p_element.get_text(strip=True)

                # p_elementの隣のpタグを取得し続けてテキストを改行とともに追加
                next_p_element = p_element.find_next_sibling()
                while True:
                    if next_p_element and next_p_element.name == 'p':
                        hr_text += '\n' + next_p_element.get_text(strip=True)
                        next_p_element = next_p_element.find_next_sibling()
                    else:
                        break

                hr_data_dict[commentUid] = hr_text

        data = []
        a_elements = soup.find_all('a')
        conversationUid = 0

        # コメントの対象テキストを処理する
        for a_element in a_elements:
            # <a>テキスト</a>がコメントの始まり箇所
            # aタグに属性がない場合は次の要素を取得
            if not a_element.attrs:
                next_sibling = a_element.find_next_sibling()
                text_data = ""
                tag_list = []  # spanタグのリスト
                p_list = []  # pタグのリスト
                p_child_list = []  # pタグの子要素のリスト
                # 次の要素がspanでありかつclassがMsoCommentReferenceか判別
                if not is_mcr(next_sibling):
                    # 次の要素が何かしらの要素がある場合
                    if next_sibling:
                        # 次の要素を取得しclassがMsoCommentReferenceか判別
                        while True:
                            if is_mcr(next_sibling) or not next_sibling:
                                break
                            else:
                                text_data += next_sibling.get_text() if next_sibling.get_text() else ""
                                tag_list.append(next_sibling)
                            next_sibling = next_sibling.find_next_sibling()
                    # 次の要素がspanでありかつclassがMsoCommentReferenceではない場合は親要素を取得
                    if not is_mcr(next_sibling):
                        next_sibling = None  # 次の要素を初期化
                        parent = a_element.find_parent()  # aタグの直前の親要素を取得
                        # 親要素を解析しその次の要素を取得
                        while True:
                            next_element = parent.find_next_sibling()
                            # 親要素がpタグならその次の要素を取得
                            if parent and parent.name == 'p':
                                if next_element:
                                    # 次の要素がpタグならその子要素を取得
                                    if next_element.name == 'p':
                                        child_text_data = ""
                                        child_list = []  # 子要素のリスト
                                        # 次の要素の子要素を取得
                                        for child in next_element.children:
                                            if is_mcr(child):
                                                next_sibling = child
                                                break  # 次の要素がspanタグかつclassがMsoCommentReferenceならforループを抜ける
                                            else:
                                                child_text_data += child.get_text() if child.get_text() else ""
                                                child_list.append(child)
                                        # child_listが空でなければp_list等に追加
                                        if child_list:
                                            text_data += child_text_data
                                            p_list.append(next_element)
                                            p_child_list.append(child_list)
                                    elif is_mcr(next_element):
                                        next_sibling = next_element
                                        break  # 次の要素がspanタグかつclassがMsoCommentReferenceならwhileループを抜ける
                                else:
                                    break  # 次の要素がなければwhileループを抜ける
                            else:
                                if is_mcr(next_element):
                                    next_sibling = next_element
                                    break  # 次の要素がspanタグかつclassがMsoCommentReferenceならwhileループを抜ける
                                else:
                                    text_data += parent.get_text() if parent.get_text() else ""
                            if is_mcr(next_sibling):
                                break  # 次の要素がspanタグかつclassがMsoCommentReferenceならwhileループを抜ける
                            else:
                                parent = parent.find_next_sibling()
                                if not parent:
                                    break  # 次の要素がなければwhileループを抜ける
                        if not is_mcr(next_sibling):
                            continue
            else:
                continue

            conversationUid += 1
            conversation_text = a_element.text + text_data
            data_info_tag = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                        'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                        'data-mce-annotation': 'tinycomments'})
            data_info_tag.string = a_element.text
            a_element.replace_with(data_info_tag)

            # tag_listが空でなければspanタグを追加
            if tag_list:
                add_span = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                       'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                       'data-mce-annotation': 'tinycomments'})
                for tag in tag_list:
                    # spanタグの子要素にtagを切り取り追加
                    add_span.append(tag.extract())
                # aタグがリプレイスされたタグの次にspanタグを追加
                data_info_tag.insert_after(add_span)

            # 改行(pタグ)がある場合はspanタグを追加
            if p_list:
                for i, p in enumerate(p_list):
                    if p_child_list[i]:
                        # 別の要素となるので毎回spanタグを作成
                        add_span = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                               'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                               'data-mce-annotation': 'tinycomments'})
                        for children in p_child_list[i]:
                            for child in children:
                                # spanタグの子要素にchildを切り取り追加
                                add_span.append(child.extract())
                        # pタグの子要素の先頭にspanタグを追加
                        p.insert(0, add_span)

            parent_data = {'conversationUid': "conversationUid_" + str(conversationUid),
                           'conversation': conversation_text, 'comments': []}

            while True:
                # 続くMsoCommentReference内のaタグからナンバリングとテキストを取得
                span_elements = next_sibling.select('span a span')
                is_span = True  # spanタグがあるか判別
                if not span_elements:
                    span_elements = next_sibling.select('span a')
                    is_span = False
                for span_element in span_elements:
                    if is_span:
                        commentUid = span_element.find_parent('a').get('id').split('_')[-1]
                    else:
                        commentUid = span_element.get('id').split('_')[-1]
                    author_text = span_element.text
                    if author_text:
                        # 元のフォーマット [名姓No.] から名姓のみ取得
                        author_text = author_text[1:-1]
                        author_text = author_text.replace(commentUid, '')
                    else:
                        author_text = None
                    comment_text = hr_data_dict.get(commentUid, '')  # hr以下のテキストを取得
                    parent_data['comments'].append(
                        {'commentUid': commentUid, 'comment': comment_text, 'author': author_text})

                # 次のspan要素を検索
                next_sibling = next_sibling.find_next_sibling()
                if next_sibling is None or next_sibling.get('class') != ['MsoCommentReference']:
                    break

            data.append(parent_data)

        # dataが空の場合はエラー
        if not data:
            return Response({'msg': '文章内に抽出対象のテキストを確認できませんでした。'}, status=status.HTTP_400_BAD_REQUEST)

        # 指定のdivを削除
        if parent_div is not None:
            parent_div.decompose()
        else:
            return Response({'msg': '文章内に抽出対象のコメントを確認できませんでした。'}, status=status.HTTP_400_BAD_REQUEST)

        # classに"MsoCommentReference"を持つ全てのspanを削除
        for span in soup.find_all('span', {'class': 'MsoCommentReference'}):
            span.decompose()

        # データを保存します
        changeUids = []

        # Conversationを登録する
        for insert_data in data:
            try:
                conversation = Conversation()
                conversation.contract_id = fetch_contract_id
                conversation.user_id = user_id
                conversation.status = Statusable.Status.ENABLE.value
                conversation.created_by_id = user_id
                conversation.updated_by_id = user_id
                conversation.created_at = now
                conversation.updated_at = now
                conversation.save()
                changeUids.append(
                    {'conversationUid': insert_data['conversationUid'], 'changeConversationUid': conversation.id}
                )
                for insert_comment in insert_data['comments']:
                    try:
                        comment = ConversationComment()
                        comment.conversation_id = conversation.id
                        comment.contract_id = fetch_contract_id
                        comment.comment = insert_comment['comment']
                        comment.user_id = user_id
                        comment.author = insert_comment['author']
                        comment.status = Statusable.Status.ENABLE.value
                        comment.created_by_id = user_id
                        comment.updated_by_id = user_id
                        comment.created_at = now
                        comment.updated_at = now
                        comment.save()
                    except DatabaseError as e:
                        logger.info(e)
                        return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)
            except DatabaseError as e:
                logger.info(e)
                return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)

        # conversationUidを変更
        for ch in changeUids:
            elements = soup.select('span[data-mce-annotation-uid="{}"]'.format(ch['conversationUid']))
            for elem in elements:
                elem['data-mce-annotation-uid'] = str(ch['changeConversationUid'])

        # 再度エンコード処理
        encoded_body = urllib.parse.quote(str(soup))
        encoded_body = base64.b64encode(encoded_body.encode('utf-8')).decode('utf-8')
        encoded_body = urllib.parse.quote(encoded_body)

        return Response({'body': encoded_body, 'data': data, 'changeUonversationUids': changeUids}, status=status.HTTP_200_OK)


def is_mcr(element):
    """
    要素がspanタグかつclassがMsoCommentReferenceか判別
    """
    if isinstance(element, Tag) and element.name == 'span' and element.get('class') == ['MsoCommentReference']:
        return True
    else:
        return False


class UploadWordFileView(APIView, GoogleCloudStorage):
    """
    Wordファイルアップロードは書式再現の問題解決までペンディング
    """
    def post(self, request):
        """
        Wordファイルをアップロードする
        アップロードされたデータを解析しHTMLへ変換しbodyへ返す
        変換時に校閲コメントがある場合はそのデータを取得しconversationへ格納
        """
        req_serializer = UploadWordFileRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = req_serializer.validated_data

        blob = data.get("blob")
        filename = blob.name
        fetch_contract_id = data.get('contract_id')
        new_version = data.get('new_version')
        datatype = File.Type.IMPORTED.value
        description = ""
        user = self.request.user
        user_id = user.id
        now = make_aware(datetime.datetime.now())
        body = None

        # docxファイルか確認
        _, ext = os.path.splitext(filename)
        if ext != ".docx":
            return Response({"msg": ["docxファイル以外はインポートできません。"]}, status=status.HTTP_400_BAD_REQUEST)

        # 紐付ける Contract を抽出しておく
        wheres = {
            'id': fetch_contract_id,
            'account': user.account
        }
        try:
            contract = Contract.objects.exclude(status=Contract.Status.DISABLE.value).filter(**wheres).get()
        except Contract.DoesNotExist as e:
            logger.info(e)
            return Response({"msg": ["契約書が見つかりません。"]}, status=status.HTTP_400_BAD_REQUEST)

        # 同じバージョンの contract_body が存在するか確認
        if ContractBody.objects.filter(contract_id=fetch_contract_id, version=new_version).first():
            return Response(
                {"msg": [
                    "同じバージョンの契約書が存在します。\n最新のメジャーバージョンまたはマイナーバージョンへ戻り、再度インポートをしてください。"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 一時ファイルを作成してBlobデータを書き込む
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
            # アップロードされたファイルの内容を一時ファイルに書き込む
            blob.seek(0)  # ファイルポインタを先頭に移動
            tmp.write(blob.read())
            tmp_path = tmp.name
        try:
            # Pandocを使用してHTMLに変換し、その出力をキャプチャ
            result = subprocess.run(
                ['pandoc', '-s', '--track-changes=all', tmp_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8'
            )
            if result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout,
                                                    stderr=result.stderr)
            html = result.stdout
            # htmlをBeautifulSoupで解析
            soup = BeautifulSoup(html, 'html.parser')
            body = soup.body

            # 画像データのエンコード
            with tempfile.TemporaryDirectory() as images_folder:
                list(extract_images_from_docx(tmp_path, images_folder))
                all_imgs = soup.find_all('img')
                if len(all_imgs) > 0:
                    for img in all_imgs:
                        image_src = img['src']
                        if image_src.startswith('media/'):
                            image_file_path = os.path.join(images_folder, os.path.basename(image_src))
                            encoded_image = encode_image_to_base64(image_file_path)
                        else:
                            # 外部画像の処理
                            try:
                                response = requests.get(image_src, timeout=30)
                                if response.status_code == 200:
                                    encoded_image = base64.b64encode(response.content).decode()
                            except Timeout:
                                logger.info(f"Timeout: {image_src}")
                                continue  # 画像のダウンロードに失敗した場合はスキップ

                        img['src'] = f"data:image/png;base64,{encoded_image}"
        except subprocess.CalledProcessError as e:
            logger.info(e)
            return Response({"msg": ["ファイルを解析できませんんでした。"]}, status=status.HTTP_400_BAD_REQUEST)
        finally:
            # 一時ファイルを削除
            os.remove(tmp_path)

        if body:
            # bodyに要素が含まれるか確認
            if not body.contents or body.text.strip() == '':
                return Response({"msg": ["ファイルを解析できませんんでした。"]}, status=status.HTTP_400_BAD_REQUEST)
            # bodyの要素を順に取得しHTMLデータとして結合して変数に格納
            body_text = ""
            for child in body.contents:
                # childがNonetypeでないかつ改行コードでない場合はchildをbody_textに追加
                if child and child != '\n':
                    body_text += str(child)
            # body_textをBeautifulSoupで解析、body_textがからの時はエラーレスポンス
            soup = BeautifulSoup(body_text, 'html.parser')
            if not soup:
                return Response({"msg": ["ファイルを解析できませんんでした。"]}, status=status.HTTP_400_BAD_REQUEST)

            # class="comment-start"のspanタグを取得
            comment_starts = soup.find_all("span", class_="comment-start")
            data = []
            parent_data = []
            conversationUid = 0
            exclude_ids = []  # 排除するidsを格納するリスト
            # comment_startsをforechで回す
            for comment_start in comment_starts:
                text_data = ""
                comments = []
                tag_list = []
                parent = None
                p_list = []
                p_child_list = []
                id = comment_start["id"] or ""
                # exclude_idsにidがある場合はcontinue
                if id in exclude_ids:
                    continue
                # comment_startのコンテンツテキストをcommentsに追加
                comments.append({
                    'commentUid': id,
                    'comment': comment_start.get_text() or "",
                    'author': comment_start["data-author"] or ""
                })
                # comment_startの次の兄弟要素を取得
                next_sibling = comment_start.next_sibling
                while True:
                    # nest_siblingがspanでclass=comment-startの場合
                    if isinstance(next_sibling, Tag) and next_sibling.name == "span" and next_sibling["class"] == ["comment-start"]:
                        # exclude_idsにnext_siblingのidを追加
                        exclude_ids.append(next_sibling["id"])
                        comments.append({
                            'commentUid': next_sibling["id"] or "",
                            'comment': next_sibling.get_text() or "",
                            'author': next_sibling["data-author"] or ""
                        })
                    # nest_siblingがspanでclass=comment-endの場合はbreak
                    elif isinstance(next_sibling, Tag) and next_sibling.name == "span" and next_sibling["class"] == ["comment-end"]:
                        break
                    elif next_sibling is None:
                        parent = comment_start.find_parent()
                        break
                    else:
                        text_data += next_sibling.get_text() if next_sibling.get_text() else ""
                        tag_list.append(next_sibling)
                    next_sibling = next_sibling.next_sibling
                # parentがnot Noneの場合
                if parent is not None:
                    while True:
                        is_end_comment = False
                        next_element = parent.next_sibling
                        # 親要素がpタグならその次の要素を取得
                        if parent and parent.name == 'p':
                            if next_element:
                                # 次の要素がpタグならその子要素を取得
                                if next_element.name == 'p':
                                    child_text_data = ""
                                    child_list = []  # 子要素のリスト
                                    # 次の要素の子要素を取得
                                    for child in next_element.children:
                                        if child.name == "span" and child["class"] == ["comment-end"]:
                                            logger.info(child["id"])
                                            is_end_comment = True
                                            break
                                        else:
                                            child_text_data += child.get_text() if child.get_text() else ""
                                            child_list.append(child)
                                    # child_listが空でなければp_list等に追加
                                    if child_list:
                                        text_data += child_text_data
                                        p_list.append(next_element)
                                        p_child_list.append(child_list)
                                elif next_element.name == "span" and next_element["class"] == ["comment-end"]:
                                    break
                            else:
                                break  # 次の要素がなければwhileループを抜ける
                        else:
                            if next_element.name == "span" and next_element["class"] == ["comment-end"]:
                                break  # 次の要素がspanタグかつclassがMsoCommentReferenceならwhileループを抜ける
                            else:
                                text_data += parent.get_text() if parent.get_text() else ""
                        if is_end_comment:
                            break  # 次の要素がspanタグかつclassがMsoCommentReferenceならwhileループを抜ける
                        else:
                            parent = parent.next_sibling
                            if not parent:
                                break  # 次の要素がなければwhileループを抜ける
                    if isinstance(next_element, Tag) and next_element.name == "span" and "comment-end" in next_element.get('class', []):
                        # whileを抜ける
                        break

                conversationUid += 1
                data_info_tag = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                            'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                            'data-mce-annotation': 'tinycomments'})
                data_info_tag.string = ""  # テキストなし
                comment_start.replace_with(data_info_tag)

                # tag_listが空でなければspanタグを追加
                if tag_list:
                    add_span = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                           'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                           'data-mce-annotation': 'tinycomments'})
                    for tag in tag_list:
                        # spanタグの子要素にtagを切り取り追加
                        if isinstance(tag, Tag):
                            add_span.append(tag.extract())
                        elif isinstance(tag, NavigableString) or isinstance(tag, str):
                            add_span.append(tag)
                    # aタグがリプレイスされたタグの次にspanタグを追加
                    data_info_tag.insert_after(add_span)

                # 改行(pタグ)がある場合はspanタグを追加
                if p_list:
                    for i, p in enumerate(p_list):
                        replace_text = ""
                        if p_child_list[i]:
                            # 別の要素となるので毎回spanタグを作成
                            add_span = soup.new_tag('span', attrs={'class': 'mce-annotation tox-comment',
                                                                   'data-mce-annotation-uid': f'conversationUid_{conversationUid}',
                                                                   'data-mce-annotation': 'tinycomments'})
                            for children in p_child_list[i]:
                                for child in children:
                                    if isinstance(child, Tag):
                                        # spanタグの子要素にchildを切り取り追加
                                        add_span.append(child.extract())
                                    elif isinstance(child, NavigableString) or isinstance(child, str):
                                        add_span.append(child)
                                        replace_text += child
                            # pタグの子要素の先頭にspanタグを追加
                            p.insert(0, add_span)

                        # replace_textを全体から削除
                        # class="comment-end"とid="id"を持つspanタグを全体から取得
                        comment_ends = soup.find_all("span", class_="comment-end", id=id)
                        # 親タグを取得
                        if comment_ends:
                            comment_end_parent = comment_ends[0].find_parent()
                            if comment_end_parent:
                                for string in comment_end_parent:
                                    if isinstance(string, NavigableString) and replace_text in string:
                                        string.extract()

                # commentsをリストに追加
                parent_data = {'conversationUid': "conversationUid_" + str(conversationUid),
                               'conversation': text_data, 'comments': comments}

                data.append(parent_data)

            # class="comment-start"のspanタグを削除
            comment_starts = soup.find_all("span", class_="comment-start")
            for comment_start in comment_starts:
                comment_start.decompose()
            # class="comment-end"のspanタグを削除
            comment_ends = soup.find_all("span", class_="comment-end")
            for comment_end in comment_ends:
                comment_end.decompose()

            # 校閲削除にスタイルを追加
            deleted = soup.find_all("span", class_="deletion")
            for delete in deleted:
                delete["style"] = "text-decoration: line-through; color: #ff0000;"

            # データを保存します
            changeUids = []

            # Conversationを登録する
            for insert_data in data:
                try:
                    conversation = Conversation()
                    conversation.contract_id = fetch_contract_id
                    conversation.user_id = user_id
                    conversation.status = Statusable.Status.ENABLE.value
                    conversation.created_by_id = user_id
                    conversation.updated_by_id = user_id
                    conversation.created_at = now
                    conversation.updated_at = now
                    conversation.save()
                    changeUids.append(
                        {'conversationUid': insert_data['conversationUid'],
                         'changeConversationUid': conversation.id}
                    )
                    for insert_comment in insert_data['comments']:
                        try:
                            comment = ConversationComment()
                            comment.conversation_id = conversation.id
                            comment.contract_id = fetch_contract_id
                            comment.comment = insert_comment['comment']
                            comment.user_id = user_id
                            comment.status = Statusable.Status.ENABLE.value
                            comment.created_by_id = user_id
                            comment.updated_by_id = user_id
                            comment.created_at = now
                            comment.updated_at = now
                            comment.save()
                        except DatabaseError as e:
                            logger.info(e)
                            return Response({"msg": ["DBエラーが発生しました。"]},
                                            status=status.HTTP_400_BAD_REQUEST)
                except DatabaseError as e:
                    logger.info(e)
                    return Response({"msg": ["DBエラーが発生しました。"]}, status=status.HTTP_400_BAD_REQUEST)

            # conversationUidを変更
            for ch in changeUids:
                elements = soup.select('span[data-mce-annotation-uid="{}"]'.format(ch['conversationUid']))
                for elem in elements:
                    elem['data-mce-annotation-uid'] = str(ch['changeConversationUid'])

            # str(soup)をutf-8に変換
            encoded_body = str(soup).encode('utf-8')

            # ファイルをGCSへアップロード
            blob.seek(0)  # ファイルポインタを先頭に移動
            try:
                self.set_user_id(user_id)
                client, bucket = self.get_cloudstorage(GCSBucketName.FILE)
                file = self.prepare_file_record(0, filename, datatype)
                _, gcs_path = self.get_gcs_fileinfo(file)
                gcs_blob = bucket.blob(gcs_path)  # GCS側
                gcs_blob.upload_from_file(blob)  # local側
                self.set_file_info(file=file, filename=filename, url=gcs_path, datatype=datatype,
                                   description=description, size=blob.size, version=new_version)
            except Exception as e:
                logger.error(f"{e}: {traceback.format_exc()}")
                return Response({"msg": "GCSへのアップロードに失敗しました。"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                self.set_user_id(0)  # クリアしておく

            # 契約書にファイルを紐付ける（save不要）
            contract.file.add(file)

            return Response({'body': encoded_body, 'data': parent_data}, status=status.HTTP_200_OK)
        else:
            return Response({"msg": ["ファイルを解析できませんんでした。"]}, status=status.HTTP_400_BAD_REQUEST)


def extract_images_from_docx(docx_path, images_folder):
    """
    docxファイルから画像を抽出する
    """
    with zipfile.ZipFile(docx_path, 'r') as docx:
        all_files = docx.namelist()
        for file in all_files:
            if file.startswith('word/media/'):
                image_path = os.path.join(images_folder, os.path.basename(file))
                with open(image_path, 'wb') as image_file:
                    image_file.write(docx.read(file))
                yield image_path


def encode_image_to_base64(image_path):
    """
    画像をbase64にエンコードする
    """
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode()
