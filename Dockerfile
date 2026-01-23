FROM python:3.11-slim

# Настройка системных переменных
ENV PYTHONUNBUFFERED=1
# Устанавливаем рабочую директорию
WORKDIR /lunch_bot

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install cryptography

# Копируем приложение
COPY tg_bot/ tg_bot/
COPY config.py .
COPY main.py .

# Команда запуска
CMD ["python3", "main.py"]
