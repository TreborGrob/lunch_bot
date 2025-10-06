import re

from tg_bot.services.days_operations import days_week
from tg_bot.services.pdf_handler import get_text_from_pdf


async def extract_category_slices(text, categories):
    category_slices = {}
    category_positions = []
    tmp_cat = ""
    # Находим все позиции категорий в тексте
    for category in categories:
        pos = text.find(category)
        if pos != -1:
            category_positions.append((pos, category))

    # Сортируем по позициям в тексте
    category_positions_sorted = sorted(category_positions, key=lambda x: x[0])

    # Извлекаем срезы
    for i, (pos, category) in enumerate(category_positions_sorted):
        start = pos
        # Ищем начало следующей категории (если есть)
        end = category_positions_sorted[i + 1][0] if i + 1 < len(category_positions_sorted) else len(text)
        category_slices[category] = text[start:end].strip()
        test_text = text[start:end].strip()
        result = test_text.split("\n1\n")
        category_slices[category] = result[1]
        if len(result) > 2:
            tmp_cat = result[2]

    # Определяем отсутствующие категории
    found_categories = set(category_slices.keys())
    all_categories = set(categories)
    missing_categories = list(all_categories - found_categories)
    if missing_categories and len(missing_categories) < 2:
        category_slices[missing_categories[0]] = tmp_cat
    return category_slices


async def extract_categories(text: str) -> list[str]:
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
    result = [category.strip() for category in categories]
    return list(set(result))


async def extract_dishes(text):
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    dishes = []

    i = 0
    while i < len(lines) - 2:
        name = lines[i]

        # Завершаем, если строка — это явно не название блюда
        if re.search(r'меню|период|действия|не является', name.lower()):
            break

        # Обработка случая "12 Корн-дог"
        if re.match(r'^\d+\s+\S+', name):
            name = re.sub(r'^\d+\s+', '', name)

        weight = lines[i+1]
        price = lines[i+2]

        # Проверяем, что вес — это последовательность чисел, разделённых "/" или "\"
        if not re.match(r'^\d+(?:[\\/]\d+)*$', weight):
            break

        # Цена должна быть числом
        if not price.isdigit():
            break

        # Пропускаем номер строки, если есть
        if i + 3 < len(lines) and re.fullmatch(r'\d+', lines[i+3]):
            i += 4
        else:
            i += 3

        dishes.append({
            "name": name,
            "weight": weight,
            "price": int(price)
        })

    return dishes


async def get_dict_with_week_category_dishes(all_text: str) -> dict:
    # Получаем категории из текста
    categories = await extract_categories(all_text)
    # Начальные индексы дней в тексте
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
