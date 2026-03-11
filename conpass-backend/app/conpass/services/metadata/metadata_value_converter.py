from datetime import datetime
from logging import getLogger
import re
from typing import Any, Tuple
import unicodedata
from jeraconv import jeraconv
from conpass.models import MetaData

logger = getLogger(__name__)


class MetadataValueConverter:

    def convert(self, metadata: MetaData) -> MetaData:
        """
        NaturalLanguageから取得したメタ情報の値を必要に応じ整形して返す
        """

        date_labels = [
            'contractdate',
            'contractstartdate',
            'contractenddate',
            'related_contract_date',
        ]

        company_name_labels = [
            'companya',
            'companyb',
            'companyc',
            'companyd',
        ]

        convert_flag_labels = ['autoupdate', 'antisocial']

        # 日付系の場合: metadataのdate_valueにYYYY-mm-dd形式で記録
        if metadata.key.label in date_labels:
            try:
                converted_date = self.convert_date(metadata.value)
                if converted_date is not None:
                    metadata.date_value = converted_date
            except ValueError as e:
                logger.info(f"{e}, value={metadata.value}, key={metadata.key.label}, contract={metadata.contract.id}")

        # 会社名の場合： metadata.valueを直接変換
        if metadata.key.label in company_name_labels:
            converted_company_name = self.convert_company_name(metadata.value)
            if converted_company_name is not None:
                metadata.value = converted_company_name

        # 自動更新の場合: 文字列の存在によって '0' or '1' のフラグに変換
        if metadata.key.label in convert_flag_labels:
            metadata.value = '1' if len(metadata.value) > 0 and metadata.value != "False" else '0'

        return metadata

    def convert_company_name(self, original_text: str) -> Any:
        """
        NaturalLanguageから取得したメタ情報の値を会社名用に整形して返す
        """
        str_company = original_text
        pattern = r'(\(|（以下).*'

        prog = re.compile(pattern)
        result = prog.search(original_text)

        if result:
            restr = result.group()
            return str_company.replace(restr, '')

        return None

    def convert_date(self, original_text: str) -> Any:
        """
        NaturalLanguageから取得したメタ情報の値を日付用に整形して返す
        """
        result = ''
        # 正規表現（西暦でハイフン、スラッシュ）
        result = self.regexp_ymd_hs(original_text)
        if result != '':
            return result

        # 正規表現（西暦で年月日）
        result = self.regexp_ymd_chchar(original_text)
        if result != '':
            return result

        # 正規表現（和暦）
        result = self.regexp_ja(original_text)
        if result != '':
            return result

        # 上記パターンで取得できない場合
        return None

    # 関数(1)_20桁までの漢数字（例：六千五百八）を数値変換する関数

    def kans2num(self, text, n=4):  # 第2引数は省略可（原則省略）
        tablekans = str.maketrans('〇一二三四五六七八九', '0123456789')
        # tablekans = str.maketrans('〇一二三四五六七八九零弐参肆伍陸漆捌玖', '01234567890123456789')
        ans = poss = 0  # ans:初期値（計算結果を加算していく）、poss:スタート位置
        tais = '京兆億万' if n == 4 else '千百十'
        n = 1 if n != 4 else 4
        text = text.translate(str.maketrans({',': None, '，': None}))
        for i in range(0, len(tais) + 1):
            pos = text.find(tais[i]) if i != len(tais) else len(text)
            if pos == -1 or (i == len(tais) and pos == poss):  # 対象となる大数が無い場合
                continue
            else:
                block = 1 if i != len(tais) and pos == poss else \
                    self.kans2num(text[poss:pos], 1) if n == 4 else \
                    int(text[poss:pos].translate(tablekans))  # 'possとposの間の漢数字を変換
            ans += block * (10 ** (n * (len(tais) - i)))
            poss = pos + 1  # possをposの次の位置に設定
        return ans

    # 関数(2)_文字列中の漢数字を算用数字に変換する関数（カンマ表示に簡易対応）
    def strkan2num(self, text):
        suuji1 = set('一二三四五六七八九十百千１２３４５６７８９123456789')  # 数字と判定する文字集合
        suuji2 = set('〇万億兆京０0,')  # 直前の文字が数字の場合に数字と判定する文字集合
        ans = tmp = ''
        num = 0
        for i in range(0, len(text) + 1):
            if i != len(text) and (text[i] in suuji1 or (tmp != '' and text[i] in suuji2)):
                tmp += text[i]  # 数字が続く限りtmpに格納
            else:  # 文字が数字でない場合
                if tmp != '':  # tmpに数字が格納されている場合
                    num = self.kans2num(tmp)
                    ans = ans + f'{num:,}' if num > 9999 else ans + str(num)  # 算用数字に変換して連結（5桁以上はカンマ区切りにフォーマット）
                    tmp = ''
                if i != len(text):
                    ans += text[i]
        return ans

    # 半角・全角スペース削除
    # Unicode正規化（全角数字→半角数字）
    # 漢数字を半角数字に変換
    def strcleansing(self, text):
        return self.strkan2num(unicodedata.normalize("NFKC", text.replace(' ', '').replace('　', '')))

    # 西暦（年月日の場合）
    def regexp_ymd_chchar(self, text):
        str_date = ''
        pattern = r'([12]\d{3})[年]([0-9]+)[月]([0-9]+)日'
        prog = re.compile(pattern)
        result = prog.search(self.strcleansing(text))

        if result:
            groups = result.groups()
            return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
        return str_date

    # 和暦の場合
    def regexp_ja(self, text):
        str_date = ''
        pattern = r'(明治|大正|昭和|平成|令和|今和)(\d{1,2})年([0-9]+)月([0-9]+)日'
        prog = re.compile(pattern)
        result = prog.search(self.strcleansing(text))

        if result:
            groups = result.groups()
            # (例)平成15年1月10日
            era_year = groups[1]  # 和暦年
            era = groups[0]
            era = era.replace('今和', '令和')

            # 和暦変換
            j2w = jeraconv.J2W()
            year = ''
            try:
                year = j2w.convert("{0}{1}年".format(era, era_year))
                month = groups[2]
                day = groups[3]
                return datetime(int(year), int(month), int(day))
            except Exception as e:
                raise ValueError(f"{e}, 和暦変換、日付変換時にエラーが発生しました")

        return str_date

    # 西暦（ハイフンとスラッシュ区切りの場合）
    def regexp_ymd_hs(self, text):
        try:
            str_date = ''
            pattern = r'([12]\d{3})[/\-]([0-9]+)[/\-]([0-9]+)'
            prog = re.compile(pattern)
            result = prog.search(self.strcleansing(text))

            if result:
                groups = result.groups()
                return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
            return str_date
        except Exception as e:
            logger.info(str(e))
            return ''

    # 対象の文字列から任意のパターンが抽出できるかチェック
    def check_pattern(self, original_text: str, pattern):
        ck = '0'
        prog = re.compile(pattern)
        result = prog.search(self.strcleansing(original_text))

        if result:
            # パターンが含まれていた場合は「1」を返す
            ck = '1'

        return ck

    # 対象の文字列から期間とその単位を抽出する場合
    def regexp_period(self, original_text):
        num = 0
        period = ''
        pattern = r'([0-9]+)(カ年|ヵ年|か年|ヶ年|ケ年|年|カ月|ヵ月|か月|ヶ月|ケ月|月|日)'
        prog = re.compile(pattern)
        result = prog.search(self.strcleansing(original_text))

        if result:
            groups = result.groups()
            num = int(groups[0])
            if groups[1] in ['カ年', 'ヵ年', 'か年', 'ヶ年', 'ケ年', '年']:
                period = 'year'
            elif groups[1] in ['カ月', 'ヵ月', 'か月', 'ヶ月', 'ケ月', '月']:
                period = 'month'
            elif groups[1] in ['日']:
                period = 'day'

        return [num, period]
