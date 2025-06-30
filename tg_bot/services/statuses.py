import enum


class StatusOrder(enum.Enum):
    CREATE = "create"
    CONFIRM = "confirm"
    CLOSE = 'close'


class StatusEmployee(enum.Enum):
    WORK = "office"
    RELAX = "relax"
