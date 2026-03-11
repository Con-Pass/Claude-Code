from enum import Enum, unique


class ContractMetaKeyIdable:
    class MetaKeyId(Enum):
        TITLE = 1  # 契約書名
        COMPANYA = 2  # 会社名（甲）
        COMPANYB = 3  # 会社名（乙）
        COMPANYC = 4  # 会社名（丙）
        COMPANYD = 5  # 会社名（丁）
        CONTRACTDATE = 6  # 契約日
        CONTRACTSTARTDATE = 7  # 契約開始日
        CONTRACTENDDATE = 8  # 契約終了日
        AUTOUPDATE = 9  # 自動更新の有無
        CANCELNOTICE = 10  # 解約ノーティス日
        DOCID = 11  # 管理番号
        RELATED_CONTRACT = 12  # 関連契約書
        RELATED_CONTRACT_DATE = 13  # 関連契約日
        CORT = 14  # 裁判所
        OUTSOURCE = 15  # 再委託禁止
        CONPASS_CONTRACT_TYPE = 16  # 契約種別
        CONPASS_PERSON = 17  # 担当者名
        CONPASS_CONTRACT_RENEW_NOTIFY = 18  # 契約更新通知
        CONPASS_AMOUNT = 19  # 金額
        ANTISOCIAL = 20  # 反社条項の有無
