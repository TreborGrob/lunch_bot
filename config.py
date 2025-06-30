import os
from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)


TOKEN = os.getenv("TOKEN")
ADMIN = int(os.getenv("ADMIN"))
NAME_BOT = os.getenv("NAME_BOT")
currency = os.getenv("currency")
FIX_SUM = int(os.getenv("FIX_SUM"))
MANAGER = os.getenv("MANAGER")
PORT_DB = int(os.getenv("PORT_DB"))
USER_DB = os.getenv("USER_DB")
PASSWORD_DB = os.getenv("PASSWORD_DB")
HOST_DB = os.getenv("HOST_DB")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_URL = f"mysql+asyncmy://{USER_DB}:{PASSWORD_DB}@{HOST_DB}/{DATABASE_NAME}"

if __name__ == '__main__':
    print('ADMIN: ', ADMIN)
    print('TOKEN: ', TOKEN)
    print('NAME_STORE: ', NAME_BOT)
