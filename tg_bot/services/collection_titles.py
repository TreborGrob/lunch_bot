import enum


class StatusOrder(enum.Enum):
    CREATE = "new"
    CONFIRM = "confirm"
    CLOSE = 'close'


class StatusEmployee(enum.Enum):
    WORK = "office"
    RELAX = "relax"


class CommandsTitle(enum.Enum):
    BALANCE = "balance"
    CREATE_BALANCE_ALL = "create_balance_all"
    UPDATE_PRICE = "update_price"
    SET_NAME = "set_name"
    CLEAR_NEXT_DAY = "clear_next_day"
    READ_LOG = "log"
    GET_USERS = "get_users"
    LUNCH_PICKER = "lunch_picker"
    SET_STATUS = "set_status"
    ADD_BREAD = "add_bread"
    COMMANDS = "commands"
    DEL_USER = "del_user"
    ADD_USER = "add_user"
    MY_ORDER = "order"
    CALENDAR = "calendar"
    MENU = "menu"
    START = "start"
    REFRESH = "refresh"
    CLEAR = "clear"
