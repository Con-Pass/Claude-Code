from enum import Enum, unique


class ContractTypeable:
    class ContractType(Enum):
        CONTRACT = 1    # 通常の契約書
        TEMPLATE = 2    # 契約書のテンプレート
        PAST = 3    # 過去契約書
