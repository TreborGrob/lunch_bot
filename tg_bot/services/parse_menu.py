import asyncio
import re

from tg_bot.services.days_operations import days_week
from tg_bot.services.pdf_handler import get_text_from_pdf


async def extract_category_slices(text, categories):
    """
    Извлекает срезы текста для каждой категории.

    Аргументы:
        text (str): исходный текст.
        categories (list): список категорий.

    Возвращает:
        dict: словарь, где ключ — название категории, а значение — соответствующий текст.
    """
    category_slices = {}

    for i, category in enumerate(categories):
        start = text.find(category)
        if start == -1:
            continue  # Пропускаем категорию, если её не нашли
        end = text.find(categories[i + 1], start) if i + 1 < len(categories) else len(text)
        category_slices[category] = text[start:end].strip()

    return category_slices


async def extract_categories(text):
    """
    Извлекает категории из текста.

    Аргументы:
        text (str): исходный текст.

    Возвращает:
        list: список категорий.
    """
    # Шаблон для поиска категорий
    pattern = r'(.*?)\n\s*Выход\s*\n\s*Цена\s*\n'

    # Ищем все совпадения и извлекаем категории
    categories = re.findall(pattern, text)

    # Убираем лишние пробелы и возвращаем список
    return [category.strip() for category in categories]


async def extract_dishes(text):
    """
    Извлекает блюда из текста.

    Аргументы:
        text (str): исходный текст.

    Возвращает:
        list: список словарей с информацией о блюдах.
    """
    # Шаблон для поиска информации о блюдах
    # pattern = r'(\d+)[\s\n](.*?)\n(\d+)\n(\d+)(?:\n|$)'
    pattern = r'(\d+)[\s\n](.*?)\n(\d+(?:/\d+)?)\n(\d+)(?:\n|$)'

    # Ищем все совпадения
    matches = re.findall(pattern, text)

    # Преобразуем данные в список словарей
    dishes = [
        {"name": match[1].strip(), "weight": match[2], "price": int(match[3])}
        for match in matches
    ]

    return dishes


async def get_dict_with_week_category_dishes(all_text: str) -> dict:
    # Поиск начальных индексов для каждого дня недели
    day_starts = {day: all_text.find(days_week[day].upper()) for day in days_week}

    # Сортируем дни недели по порядку
    sorted_days = sorted(day_starts.keys())

    # Создаем срезы текста для каждого дня недели
    day_texts = {}
    for i, day in enumerate(sorted_days):
        start = day_starts[day]
        end = day_starts[sorted_days[i + 1]] if i + 1 < len(sorted_days) else len(all_text)
        day_texts[days_week[day]] = all_text[start:end].strip()

    # Обработка каждого дня недели
    all_dishes = {}
    for day, day_text in day_texts.items():
        categories = await extract_categories(day_text)
        category_slices = await extract_category_slices(day_text, categories)
        day_dishes = {category: await extract_dishes(dishes_text) for category, dishes_text in category_slices.items()}
        all_dishes[day] = day_dishes

    return all_dishes


async def get_dict_all_dishes(path_pdf_file: str) -> dict | bool:
    template = {'Понедельник': {}, 'Вторник': {}, 'Среда': {}, 'Четверг': {}, 'Пятница': {}, 'Суббота': {},
                'Воскресенье': {}}
    text = get_text_from_pdf(path_pdf_file)
    dict_dishes = await get_dict_with_week_category_dishes(text)
    if dict_dishes != template:
        return dict_dishes
    return False


async def test_pdf_get_text():
    pdf_file = "C:\\Users\\Grob\\Documents\\МЕНЮ ДЛЯ КЛИЕНТОВ ИЮНЬ-ИЮЛЬ 24 г..pdf"
    text = get_text_from_pdf(pdf_file)
    dict_dishes = await get_dict_with_week_category_dishes(text)
    print(dict_dishes)


async def test_day(day: str) -> dict:
    pdf_file = "C:\\Users\\Grob\\Documents\\МЕНЮ ПОСТНОЕ 2025 Г..pdf"
    all_text: str = get_text_from_pdf(pdf_file)
    """
    Извлекает информацию о блюдах для указанного дня недели.

    Аргументы:
        all_text (str): Исходный текст.
        day (str): День недели, для которого нужно извлечь данные.

    Возвращает:
        dict: Словарь с категориями и блюдами для указанного дня.
    """
    days_week = {
        "понедельник": "ПОНЕДЕЛЬНИК",
        "вторник": "ВТОРНИК",
        "среда": "СРЕДА",
        "четверг": "ЧЕТВЕРГ",
        "пятница": "ПЯТНИЦА",
        "суббота": "СУББОТА",
        "воскресенье": "ВОСКРЕСЕНЬЕ",
    }

    if day.lower() not in days_week:
        raise ValueError("Некорректный день недели")

    day_upper = days_week[day.lower()]
    start = all_text.find(day_upper)
    if start == -1:
        raise ValueError(f"День '{day}' не найден в тексте")

    next_days = list(days_week.values())
    next_index = next_days.index(day_upper) + 1
    end = all_text.find(next_days[next_index], start) if next_index < len(next_days) else len(all_text)

    day_text = all_text[start:end].strip()
    categories = await extract_categories(day_text)
    category_slices = await extract_category_slices(day_text, categories)
    print(category_slices)
    day_dishes = {category: await extract_dishes(dishes_text) for category, dishes_text in category_slices.items()}

    return {day: day_dishes}


async def test_extract_dishes():
    text = ('Вторые блюда\nВыход \nЦена\n1\nКуриная котлета\n60\n40\n2\nКуриная котлета паровая\n70\n62\n3\n'
            'Куриная грудка с помидорами\n70\n87\n4\nБедро кур. жареное\n130\n103\n5\n'
            'Курица в соусе Том ям\n70/20\n105\n6\nКуриная грудка сувид\n50\n89\n7\nТефтели с тыквой\n70\n69\n8\n'
            'Печень по-деревенски с луком\n45/15\n76\n9\nТефтели из горбуши в молочном соусе\n70/30\n82\n10 '
            'Пикша в томатном соусе\n60/30\n92')
    dishes = await extract_dishes(text)
    print(dishes)
    return dishes


if __name__ == "__main__":
    # print(asyncio.run(test_day("Понедельник")))
    asyncio.run(test_extract_dishes())
