import logging
import os
from logging.handlers import RotatingFileHandler

import aiofiles


async def tail(file_path, num_lines):
    lines = []
    total_chars = 0

    async with aiofiles.open(file_path, mode='r') as file:
        file_lines = await file.readlines()
        for line in reversed(file_lines):
            line = line.strip()
            line_length = len(line)

            if total_chars + line_length > 3800:
                break

            lines.insert(0, line)
            total_chars += line_length

            if len(lines) >= num_lines:
                break

    return '\n'.join(lines)


def setup_logging():
    # Создаем директорию для логов, если её нет
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Настройка формата логов
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Создаем RotatingFileHandler с максимальным размером 4 МБ
    log_file = os.path.join(log_dir, "bot.log")
    handler = RotatingFileHandler(
        log_file, maxBytes=4 * 1024 * 1024, backupCount=1, encoding="utf-8"
    )
    handler.setFormatter(formatter)

    # Настройка уровня логирования
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Удаляем старые логи, если они превышают backupCount
    if os.path.exists(log_file + ".1"):
        os.remove(log_file + ".1")
