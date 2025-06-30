FROM python:3.11-slim
# Устанавливаем переменные окружения
ENV TOKEN 6991960701:AAGvZixHApdQ_lu1scXts2_ib-7rhiWY0Ak
ENV ADMIN 6933142814
ENV PYTHONUNBUFFERED 1
ENV MANAGER 6933142814
ENV FIX_SUM 200
ENV currency ₽
ENV LOG_FILE lunch.log
ENV PORT_DB 3306
ENV USER_DB grob
ENV PASSWORD_DB 603811Grob!
ENV HOST_DB localhost
ENV DATABASE_NAME lunch

# Устанавливаем рабочую директорию
WORKDIR /lunch_bot
# Копируем файл requirements.txt и устанавливаем зависимости
COPY requirements.txt .

RUN pip install -r requirements.txt
# Копируем только нужные файлы и папку
COPY tg_bot/ tg_bot/
COPY config.py .
COPY main.py .
# Запускаем приложение
CMD ["python3", "main.py"]
