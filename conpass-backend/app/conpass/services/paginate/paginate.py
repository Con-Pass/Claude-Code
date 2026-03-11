import math

from django.conf import settings
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from collections import OrderedDict


class StandardResultsSetPagination(PageNumberPagination):
    """
    検索画面のページネーション
    get_paginated_responseメソッドにpage_countを追加
    """
    page_size = settings.REST_FRAMEWORK['PAGE_SIZE']

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('page_number', self.page.number),  # 現在のページ
            ('page_total', self.page.paginator.count),  # 全レコード数
            ('next', self.get_next_link()),  # 次ページのurl
            ('previous', self.get_previous_link()),  # 前ページのurl
            ('results', data),  # 現在のページデータ
            ('page_count', math.ceil(self.page.paginator.count / self.page_size))  # 全ページ数
        ]))
