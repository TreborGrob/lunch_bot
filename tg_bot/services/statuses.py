import enum


class StatusOrder(enum.Enum):
    CREATE = "new"
    CONFIRM = "confirm"
    CLOSE = 'close'


class StatusEmployee(enum.Enum):
    WORK = "office"
    RELAX = "relax"
