from enum import Enum, unique


class ContractStatusable:
    class Status(Enum):
        DISABLE = 0  # 無効
        ENABLE = 1  # 有効
        UNUSED = 10  # 未採用（契約書テンプレート用）
        USED = 11  # 採用済（契約書テンプレート用）
        IN_PROCESS = 20  # 仕掛中
        SIGNED = 21  # 署名済
        FINISH = 22  # 名称未定・ワークフロー完了
        SIGNED_BY_PAPER = 23  # 名称未定
        CANCELED = 30  # 解約
        EXPIRED = 31  # 契約満了
