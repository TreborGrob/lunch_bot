import asyncio
import json
import os
from datetime import datetime
import requests
from openpyxl import load_workbook
from datetime import timedelta


def download_calendar_excel(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Проверка на ошибки HTTP

        # Определение полного пути для сохранения файла
        file_name = 'calendar.xlsx'
        full_path = os.path.abspath(file_name)

        with open(full_path, 'wb') as file:
            file.write(response.content)

        return full_path  # Возвращаем полный путь до файла

    except (requests.RequestException, OSError) as e:
        print(f"Ошибка при скачивании или сохранении файла: {e}")
        return False  # Возвращаем False при ошибке


def get_year():
    year = datetime.now().year
    return year


days_week = {0: "Понедельник",
             1: "Вторник",
             2: "Среда",
             3: "Четверг",
             4: "Пятница",
             5: "Суббота",
             6: "Воскресенье"}

day_rows = [(6, 12), (19, 25), (32, 38), (45, 51)]

months_columns = {
    1: (1, 8),
    2: (8, 14),
    3: (14, 20),
    4: (1, 8),
    5: (8, 14),
    6: (14, 20),
    7: (1, 8),
    8: (8, 14),
    9: (14, 20),
    10: (1, 8),
    11: (8, 14),
    12: (14, 20)
}


def tomorrow_day_name(week):
    current_datetime = datetime.now()
    return week[current_datetime.weekday() + 1]


def tomorrow_day_int():
    current_datetime = datetime.now()
    return current_datetime.weekday() + 1


async def load_year_days():
    """Загружает данные из year_days.json."""
    file_name = "year_days.json"
    full_path = os.path.abspath(file_name)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Файл {file_name} не найден.")

    with open(full_path, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            raise ValueError(f"Ошибка чтения данных из файла {file_name}. Файл поврежден.")


async def next_work_day_string():
    """Возвращает следующую рабочую дату в строковом формате."""
    try:
        year_days = await load_year_days()
    except (FileNotFoundError, ValueError) as e:
        print(f"Ошибка загрузки данных: {e}")
        return False

    current_date = datetime.now() + timedelta(days=1)

    while True:
        current_date_str = current_date.strftime('%Y-%m-%d')
        current_year = current_date.year
        # Если дата рабочая, возвращаем её
        if not year_days.get(str(current_year), {}):
            return False
        if current_date_str in year_days.get(str(current_year), {}).get("work", []):
            return current_date_str

        # Если год вышел за пределы текущего, прекращаем поиск
        # if current_date.year != current_year:
        #     return False

        # Иначе прибавляем день
        current_date += timedelta(days=1)


def create_matrix_system(start_row, end_row, start_col, end_col):
    matrix = []
    for row in range(start_row, end_row + 1):
        # Создаем список для текущей строки
        current_row = []
        # Перебираем столбцы от start_col до end_col
        for col in range(start_col, end_col + 1):
            # Добавляем кортеж (номер строки, номер столбца)
            current_row.append((row, col))
        # Добавляем текущую строку в матрицу
        matrix.append(current_row)
    return matrix


def parse_calendar(file_path, sheet_name, year, months_matrix):
    # Загружаем Excel файл с помощью openpyxl
    wb = load_workbook(file_path, data_only=True)
    sheet = wb[sheet_name]
    year_days = {}
    work_days = []
    non_work_days = []

    # Проверяем существующий JSON файл
    file_name = "year_days.json"
    full_path = os.path.abspath(file_name)

    if os.path.exists(full_path):
        with open(full_path, "r") as file:
            year_days = json.load(file)

    # Проходим по каждому месяцу
    for month, weeks in months_matrix.items():
        for week in weeks:  # Проходим по неделям
            for (row, col) in week:  # И по дням недели
                # Получаем значение ячейки
                cell = sheet.cell(row=row, column=col)
                cell_value = cell.value

                if cell_value is None:
                    continue  # Если ячейка пуста, пропускаем

                # Парсим значение как день
                try:
                    if isinstance(cell_value, str):  # Проверяем, является ли cell_value строкой
                        day = int(cell_value.rstrip('*'))  # Удаляем '*' и преобразуем в int
                    else:
                        day = int(cell_value)  # Если это уже число, просто преобразуем в int
                    day_str = f"{day:02d}"
                    date = f"{year}-{month:02d}-{day_str}"

                    # Проверяем цвет текста
                    font_color = cell.font.color
                    if font_color is not None:
                        rgb_color = font_color.rgb
                        if rgb_color == "FFFF0000":  # Красный цвет (нерабочий день)
                            non_work_days.append(date)
                        else:  # Остальные цвета - рабочий
                            work_days.append(date)
                    else:
                        # Если цвета нет, считаем, что день рабочий
                        work_days.append(date)

                except ValueError:
                    continue  # Если не можем распарсить день, пропускаем

    # Обновляем данные для текущего года
    year_days[str(year)] = {
        "work": sorted(work_days),
        "non_work": sorted(non_work_days)
    }

    # Сохраняем обновленные данные в файл
    with open(full_path, "w") as file:
        json.dump(year_days, file, indent=4, ensure_ascii=False)

    return full_path


def create_matrices():
    # Создаем словарь для хранения матриц каждого месяца
    months_matrices = {}

    # Создаем матрицы для каждого месяца
    for month, (col_start, col_end) in months_columns.items():
        # Определяем, какой диапазон строк использовать (каждые 3 месяца общий)
        row_start, row_end = day_rows[(month - 1) // 3]

        # Создаем матрицу для текущего месяца
        matrix = []
        for row in range(row_start, row_end + 1):
            current_row = []
            for col in range(col_start, col_end + 1):
                current_row.append((row, col))
            matrix.append(current_row)

        # Добавляем матрицу в словарь
        months_matrices[month] = matrix

    return months_matrices


async def get_day_of_week(date_string):
    # Преобразуем строку в объект даты
    date_obj = datetime.strptime(date_string, '%Y-%m-%d')
    # Возвращаем день недели (понедельник = 1, воскресенье = 7)
    return date_obj.isoweekday()


async def test_calendar():
    months_matrix = create_matrices()
    file_calendar = download_calendar_excel("https://mtsz.tatarstan.ru/file/pub/pub_4334893.xlsx")
    # Получение списков
    parse_calendar(file_calendar, "Лист1", 2025, months_matrix)

# Пример использования
if __name__ == "__main__":
    # url_calendar = "https://mtsz.tatarstan.ru/file/pub/pub_3903989.xlsx"
    # months_matrix = create_matrices()
    # file_calendar = download_calendar_excel(url_calendar)
    # Получение списков
    # parse_calendar(file_calendar, "Лист1", 2024, months_matrix)
    print(asyncio.run(test_calendar()))

