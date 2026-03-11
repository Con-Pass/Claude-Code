from enum import Enum, unique


class Statusable:
    class Status(Enum):
        DISABLE = 0
        ENABLE = 1
