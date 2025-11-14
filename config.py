import os
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


TOKEN = os.getenv("TOKEN")
ADMIN = int(os.getenv("ADMIN"))
MANAGER = int(os.getenv("MANAGER"))
NAME_BOT = os.getenv("NAME_BOT")
currency = os.getenv("currency")
FIX_SUM = int(os.getenv("FIX_SUM"))
PORT_DB = int(os.getenv("PORT_DB"))
USER_DB = os.getenv("USER_DB")
PASSWORD_DB = os.getenv("PASSWORD_DB")
HOST_DB = os.getenv("HOST_DB")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_URL = f"mysql+asyncmy://{USER_DB}:{PASSWORD_DB}@{HOST_DB}:{PORT_DB}/{DATABASE_NAME}"
LAST_HOUR_FOR_ORDER: int = 14
LAST_MINUTE_FOR_ORDER: int = 00
HOUR_OPEN_ORDER: int = 1
REMINDER_HOUR: int = 12
REMINDER_MINUTES: int = 30
TIMEZONE = "Europe/Moscow"
REMINDER_TEXT_HOUR = "13"
REMINDER_TEXT_MINUTES = "00"
MIN_AMOUNT_ORDER = 110
ACCESS_ARRAY = ("admin", "manager")

if __name__ == '__main__':
    print('ADMIN: ', ADMIN)
    print('TOKEN: ', TOKEN)
    print('NAME_STORE: ', NAME_BOT)
    print('DATABASE_URL: ', DATABASE_URL)
