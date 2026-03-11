from datetime import datetime
from dateutil.relativedelta import relativedelta
from lib2to3.pytree import convert
from app.conpass.services.metadata.metadata_value_converter import MetadataValueConverter
from app.conpass.tests.factories.contract import ContractFactory
from app.conpass.tests.factories.meta_data import MetaDataFactory
from app.conpass.tests.factories.meta_key import MetaKeyFactory
import pytest

from conpass.models import MetaData


class TestMetadataValueConverter:
    @pytest.mark.parametrize('case,date_string,expected', [
        ['西暦_有効_ゼロ埋めなし', '2022年1月2日', datetime(2022, 1, 2)],
        ['西暦_有効_ゼロ埋めあり', '2022年02月03日', datetime(2022, 2, 3)],
        ['西暦_有効_前後に空白', ' 2022年12月10日 ', datetime(2022, 12, 10)],
        ['西暦_有効_前後に余分な文字', 'A2022年12月02日A', datetime(2022, 12, 2)],
        ['西暦_無効_西暦年桁数3桁', '202年1月2日', None],
        ['西暦_無効_西暦年桁数5桁', '20212年1月2日', None],
        ['西暦_無効_月桁数3桁', '2022年123月2日', None],
        ['西暦_無効_13月', '2022年13月2日', None],
        ['西暦_無効_日桁数3桁', '2022年12月123日', None],
        ['西暦_無効_32日', '2022年12月32日', None],
        ['ハイフン区切り_有効_ゼロ埋めなし', '2022-03-04', datetime(2022, 3, 4)],
        ['ハイフン区切り_有効_ゼロ埋めあり', '2022-05-06', datetime(2022, 5, 6)],
        ['ハイフン区切り_有効_前後に空白', ' 2022-12-10 ', datetime(2022, 12, 10)],
        ['ハイフン区切り_有効_前後に余分な文字', 'A2022-12-02A', datetime(2022, 12, 2)],
        ['ハイフン区切り_無効_西暦年桁数3桁', '202-1-2', None],
        ['ハイフン区切り_無効_西暦年桁数5桁', '20212-1-2', None],
        ['ハイフン区切り_無効_月桁数3桁', '2022-123-2', None],
        ['ハイフン区切り_無効_13月', '2022-13-2', None],
        ['ハイフン区切り_無効_日桁数3桁', '2022-12-123', None],
        ['ハイフン区切り_無効_32日', '2022-12-32', None],
        ['スラッシュ区切り_有効_ゼロ埋めなし', '2022/03/04', datetime(2022, 3, 4)],
        ['スラッシュ区切り_有効_ゼロ埋めあり', '2022/05/06', datetime(2022, 5, 6)],
        ['スラッシュ区切り_有効_前後に空白', ' 2022/12/10 ', datetime(2022, 12, 10)],
        ['スラッシュ区切り_有効_前後に余分な文字', 'A2022/12/02A', datetime(2022, 12, 2)],
        ['スラッシュ区切り_無効_西暦年桁数3桁', '202/1/2', None],
        ['スラッシュ区切り_無効_西暦年桁数5桁', '20212/1/2', None],
        ['スラッシュ区切り_無効_月桁数3桁', '2022/123/2', None],
        ['スラッシュ区切り_無効_13月', '2022/13/2', None],
        ['スラッシュ区切り_無効_日桁数3桁', '2022/12/123', None],
        ['スラッシュ区切り_無効_32日', '2022/12/32', None],
        ['和暦_有効_ゼロ埋めなし', '令和1年2月3日', datetime(2019, 2, 3)],
        ['和暦_有効_ゼロ埋めあり', '平成01年02月03日', datetime(1989, 2, 3)],
        ['和暦_有効_前後に空白', ' 令和01年3月4日 ', datetime(2019, 3, 4)],
        ['和暦_有効_前後に余分な文字', 'A令和01年12月02日A', datetime(2019, 12, 2)],
        ['和暦_有効_令和', '令和01年2月10日', datetime(2019, 2, 10)],
        ['和暦_有効_「今和」', '今和01年02月10日', datetime(2019, 2, 10)],
        ['和暦_有効_平成', '平成01年2月11日', datetime(1989, 2, 11)],
        ['和暦_有効_昭和', '昭和01年2月12日', datetime(1926, 2, 12)],
        ['和暦_有効_大正', '大正01年2月13日', datetime(1912, 2, 13)],
        ['和暦_無効_年桁数3桁', '平成123年1月2日', None],
        ['和暦_無効_月桁数3桁', '平成10年123月2日', None],
        ['和暦_無効_13月', '平成10年13月2日', None],
        ['和暦_無効_日桁数3桁', '令和4年12月123日', None],
        ['和暦_無効_32日', '令和3年12月32日', None],
        ['スペースが入ってるパターン', '平成28年11月 25 日', datetime(2016, 11, 25)],
        ['スペースが入ってるパターン_後に余分な文字', '平成18年 11月 30日まで', datetime(2006, 11, 30)],
        ['スペースが入ってるパターン_後に余分な文字', '2022 年 6 月　30 日まで', datetime(2022, 6, 30)],
    ])
    def test__convert_date(self, case, date_string, expected):
        """
        有効な日付はdatetime、無効な日付はNoneに変換されること
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.build()
        metadata = MetaDataFactory.build(
            contract=contract,
            value=date_string,
            date_value=None,
            key=(MetaKeyFactory.build(label='contractenddate')),
        )

        converted = converter.convert(metadata)

        assert converted.date_value == expected, case

    @pytest.mark.parametrize('case,label,expected', [
        ['変換対象__契約日', 'contractstartdate', datetime(2022, 1, 1)],
        ['変換対象__契約開始日', 'contractstartdate', datetime(2022, 1, 1)],
        ['変換対象__契約終了日', 'contractenddate', datetime(2022, 1, 1)],
        ['変換対象__解約ノーティス日', 'cancelnotice', datetime(2022, 1, 1)],
        ['変換対象外__契約名', 'title', None],
    ])
    def test__convert_date_label(self, case, label, expected):
        """
        日付の変換は日付系のメタ情報の場合のみ変換が行われること
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.build()
        metadata = MetaDataFactory.build(
            contract=contract,
            value='2022-01-01',
            date_value=None,
            key=(MetaKeyFactory.build(label=label)),
        )

        converted = converter.convert(metadata)

        assert converted.date_value == expected, f"{case}({label})"

    @pytest.mark.parametrize('case,company_name,expected', [
        ['会社名_余分な文言含む_パターン1', '株式会社ABC(以下、「甲」という。)', '株式会社ABC'],
        ['会社名_余分な文言含む_パターン2', '株式会社DEF(以下「甲」という)と及び甲のグループ各社', '株式会社DEF'],
        ['会社名_余分な文言含む_パターン3', '株式会社A、株式会社B、株式会社C(以下、3社を「甲」という)', '株式会社A、株式会社B、株式会社C'],
        ['会社名_余分な文言含む_パターン4', '株式会社D(以下「受注者」という。)', '株式会社D'],
    ])
    def test__convert_company_name(self, case, company_name, expected):
        """
        会社名に「(以下、「甲」という。)」等の文言が含まれる場合カットすること
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.build()
        metadata = MetaDataFactory.build(
            contract=contract,
            value=company_name,
            key=(MetaKeyFactory.build(label='companya')),
        )

        converted = converter.convert(metadata)

        assert converted.value == expected, case

    @pytest.mark.django_db
    @pytest.mark.parametrize('case,label,expected', [
        ['変換対象_会社名（甲）', 'companya', '株式会社A'],
        ['変換対象_会社名（乙）', 'companyb', '株式会社A'],
        ['変換対象_会社名（丙）', 'companyc', '株式会社A'],
        ['変換対象_会社名（丁）', 'companyd', '株式会社A'],
        ['変換対象_契約書名', 'title', '株式会社A(以下、「甲」という。)'],
    ])
    def test__convert_company_name_label(self, case, label, expected):
        """
        日付の変換は日付系のメタ情報の場合のみ変換が行われること
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.create()
        metadata = MetaDataFactory.create(
            contract=contract,
            value="株式会社A(以下、「甲」という。)",
            key=(MetaKeyFactory.create(label=label)),
        )

        converted = converter.convert(metadata)

        assert converted.value == expected, f"{case}({label})"

    @pytest.mark.django_db
    @pytest.mark.parametrize('case,label,data,expected', [
        ['変換対象_文字列あり', 'autoupdate', '同一内容にて更に12ヶ月延長されるものとし', '1'],
        ['変換対象_空文字列', 'autoupdate', '', '0'],
    ])
    def test_convert_autoupdate_label(self, case, label, data, expected):
        """
        契約更新通知は文字列がある場合は「通知あり(1)」を設定して、文字列がない場合は「通知なし(0)」を設定すること
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.create()
        metadata = MetaDataFactory.create(
            contract=contract,
            value=data,
            key=(MetaKeyFactory.create(label=label)),
        )

        converted = converter.convert(metadata)

        assert converted.value == expected, case

    @pytest.mark.django_db
    @pytest.mark.parametrize('case,label,data,expected', [
        ['変換対象_空文あり', 'contractenddate', '開始日より１年間で', datetime(2022, 5, 31)],
        ['変換対象_空文あり', 'contractenddate', '開始日より6ヶ月間で', datetime(2021, 11, 30)],
        ['変換対象_空文あり', 'contractenddate', '開始日より６ヶ月間で', datetime(2021, 11, 30)],
        ['変換対象_空文あり', 'contractenddate', '開始日より六ヶ月間で', datetime(2021, 11, 30)],
        ['変換対象_空文あり', 'contractenddate', '締結日より 32　日間で', datetime(2023, 1, 2)],
        ['変換対象_空文あり', 'contractenddate', '締結日より 3カ月で', datetime(2023, 2, 28)],
        ['変換対象_空文なし', 'contractenddate', '１年間', None],
    ])
    def test_convert_contractenddate_label(self, case, label, data, expected):
        """
        契約終了日の文字列から対象のパターンが抽出し処理するテスト
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.create()
        metadata = MetaDataFactory.create(
            contract=contract,
            value=data,
            date_value=None,
            key=(MetaKeyFactory.create(label=label)),
        )

        converted = converter.convert(metadata)

        # 契約終了日を処理する
        cd_reckoning_dates = [datetime(2022, 12, 1), datetime(2023, 1, 4)]
        csd_reckoning_dates = [datetime(2023, 1, 4), datetime(2022, 2, 1), datetime(2021, 6, 1)]
        reckoning_dates = []
        contract_period = []
        if converted.value is not None:
            metadata_value_converter = MetadataValueConverter()
            if metadata_value_converter.check_pattern(converted.value, r'(締結日|締結の日|締結後|本日|発行日|西暦)') == '1':
                # 契約日が取得できているか判断する
                if cd_reckoning_dates:
                    reckoning_dates = sorted(cd_reckoning_dates)  # 昇順で起算日リストをソートする
            elif metadata_value_converter.check_pattern(converted.value, r'(開始|開始する)日') == '1':
                # 契約開始日が取得できているか判断する
                if csd_reckoning_dates:
                    reckoning_dates = sorted(csd_reckoning_dates)  # 昇順で起算日リストをソートする
            if reckoning_dates:
                # 契約終了日の文字列の中に期間が含まれているか判断する
                if metadata_value_converter.check_pattern(converted.value, r'([0-9]+)(年|カ月|か月|ヶ月|ケ月|月|日)') == '1':
                    contract_period = metadata_value_converter.regexp_period(converted.value)
                    if contract_period and contract_period[0] > 0:
                        if contract_period[1] == 'year':
                            # 年数を加算して1日減算する
                            converted.date_value = reckoning_dates[0] + relativedelta(years=contract_period[0]) + relativedelta(days=-1)
                        elif contract_period[1] == 'month':
                            # 月数を加算して1日減算する
                            converted.date_value = reckoning_dates[0] + relativedelta(months=contract_period[0]) + relativedelta(days=-1)
                        elif contract_period[1] == 'day':
                            converted.date_value = reckoning_dates[0] + relativedelta(days=contract_period[0])

        assert converted.date_value == expected, case

    @pytest.mark.django_db
    @pytest.mark.parametrize('case,label,data,expected', [
        ['変換対象_空文なし', 'cancelnotice', '開始日より１カ月で', None],
        ['変換対象_空文あり', 'cancelnotice', '2ヶ月間前までに', datetime(2023, 4, 30)],
        ['変換対象_空文あり', 'cancelnotice', '終了日より 1ヶ月前迄に', datetime(2023, 5, 30)],
        ['変換対象_空文なし', 'cancelnotice', '２カ月で', None],
        ['変換対象_空文あり', 'cancelnotice', '３ ヶ月以上前', datetime(2023, 3, 30)],
        ['変換対象_空文なし', 'cancelnotice', '2ヵ月前の予告', datetime(2023, 4, 30)],
        ['変換対象_空文なし', 'cancelnotice', '１ヵ年前の予告', datetime(2022, 6, 30)],
        ['変換対象_空文なし', 'cancelnotice', '一ヵ年前の予告', datetime(2022, 6, 30)],
        ['変換対象_空文なし', 'cancelnotice', '1ヵ年前の予告', datetime(2022, 6, 30)],
    ])
    def test_convert_cancelnotice_label(self, case, label, data, expected):
        """
        契約終了日の日付と解約ノーティスの文字列から対象のパターンを抽出し処理するテスト
        """
        converter = MetadataValueConverter()

        contract = ContractFactory.create()
        metadata = MetaDataFactory.create(
            contract=contract,
            value=data,
            date_value=None,
            key=(MetaKeyFactory.create(label=label)),
        )

        converted = converter.convert(metadata)

        # cancelnoticeを処理する
        ced_date_values = [datetime(2023, 6, 30), datetime(2023, 6, 30), datetime(2023, 6, 30)]
        if ced_date_values and ced_date_values.count(ced_date_values[0]) == len(ced_date_values) and converted.value is not None:
            metadata_value_converter = MetadataValueConverter()
            if metadata_value_converter.check_pattern(converted.value, r'([0-9]+)(カ年|ヵ年|か年|ヶ年|ケ年|年|カ月|ヵ月|か月|ヶ月|ケ月|月)') == '1':
                if metadata_value_converter.check_pattern(converted.value, r'(迄|まで|前|まえ|以上)') == '1':
                    notice_period = metadata_value_converter.regexp_period(converted.value)
                    if notice_period and notice_period[0] > 0:
                        if notice_period[1] == 'year':
                            # 年数を減算する
                            converted.date_value = ced_date_values[0] + relativedelta(years=-notice_period[0])
                        elif notice_period[1] == 'month':
                            # 月数を減算する
                            converted.date_value = ced_date_values[0] + relativedelta(months=-notice_period[0])

        assert converted.date_value == expected, case
