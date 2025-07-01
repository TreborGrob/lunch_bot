FROM python:3.11-slim

# Настройка системных переменных
ENV PYTHONUNBUFFERED=1 \
    FIX_SUM=200 \
    currency=₽ \
    LOG_FILE=lunch.log

# Устанавливаем рабочую директорию
WORKDIR /lunch_bot

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install -r requirements.txt

# Копируем приложение
COPY tg_bot/ tg_bot/
COPY wait-for-mysql.sh /wait-for-mysql.sh
COPY config.py .
COPY main.py .

# Команда запуска
CMD ["python3", "main.py"]
