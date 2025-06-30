import asyncio
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from tg_bot.essence.dishes import DishData
from tg_bot.essence.groups import Group


async def dishes_in_side_items(dishes: list, session: AsyncSession) -> defaultdict:
    """
    Группирует блюда по категориям и комбинирует их с добавками.
    Возвращает словарь с итоговыми комбинациями блюд и их количеством.

    :param dishes: Список блюд в формате [{'dish': DishData, 'count': int}]
    :param session: Асинхронная сессия SQLAlchemy
    :return: Словарь {комбинация_блюд: количество}
    """
    # Получаем группы блюд
    group_table = Group(session)
    groups = await group_table.get_all_groups()
    ids_groups = {group.id: group.name for group in groups}

    # Инициализация категорий
    categories = {
        'garnishes': [],  # Гарниры
        'mains': [],  # Основные блюда
        'soups': [],  # Супы
        'sup_garnish': [],  # Добавки к гарниру
        'sup_syrnik': [],  # Добавки к сырникам
        'sup_soup': [],  # Добавки к супам
        'syrniki_count': 0,  # Количество сырников
        'smetana_count': 0  # Количество сметаны
    }
    dish_counter = defaultdict(int)

    # Распределение блюд по категориям
    for item in dishes:
        dish = item['dish']
        count = item['count']
        group_name = ids_groups.get(dish.group_id, '')

        if 'каша' in dish.name.lower() or group_name == 'Гарниры':
            categories['garnishes'].append((dish.name, count))
        elif group_name == 'Вторые блюда':
            categories['mains'].append((dish.name, count))
        elif group_name == 'Первые блюда':
            categories['soups'].append((dish.name, count))
        elif group_name == 'Добавки':
            if 'сметана' in dish.name.lower().split():
                categories['smetana_count'] += count
            elif dish.name.lower() in ['зелень', 'гренки']:
                categories['sup_soup'].append((dish.name, count))
            elif dish.name.lower() in ['мед', 'сгущенка', 'мёд', 'сгущёнка']:
                categories['sup_syrnik'].append((dish.name, count))
            else:
                categories['sup_garnish'].append((dish.name, count))
        elif 'сосиска' in dish.name.lower() or 'купаты' in dish.name.lower():
            categories['mains'].append((dish.name, count))
        elif dish.name.lower() == 'сырник':
            categories['syrniki_count'] += count
        else:
            dish_counter[dish.name] += count

    # Обработка супов с добавками
    for soup, soup_count in categories['soups']:
        combined_sides = [side for side, side_count in categories['sup_soup'] if side_count > 0]
        for _ in range(soup_count):
            text = soup
            if "борщ" in soup.lower().split() and categories['smetana_count'] > 0:
                text += " + Сметана"
                categories['smetana_count'] -= 1
            if combined_sides:
                text += f" + {' + '.join(combined_sides)}"
                categories['sup_soup'].clear()
            dish_counter[text] += 1

    # Обработка гарниров с добавками и основными блюдами
    for garnish, garnish_count in categories['garnishes']:
        combined_sides = [side for side, side_count in categories['sup_garnish'] if side_count > 0]
        for _ in range(garnish_count):
            text = garnish
            if categories['mains']:
                main, main_count = categories['mains'].pop(0)
                text += f" + {main}"
                if main_count > 1:
                    text += f" * {main_count}"
            if combined_sides:
                text += f" + {' + '.join(combined_sides)}"
                categories['sup_garnish'].clear()
            dish_counter[text] += 1

    # Добавление оставшихся основных блюд
    for main, main_count in categories['mains']:
        if main_count > 0:
            dish_counter[main] += main_count

    # Обработка сырников с добавками
    if categories['syrniki_count'] > 0:
        syrniki_line = "Сырник" if categories['syrniki_count'] == 1 else f"{categories['syrniki_count']} Сырника"
        if categories['smetana_count'] > 0:
            syrniki_line += " + Сметана"
            if categories['smetana_count'] > 1:
                syrniki_line += f" * {categories['smetana_count']}"
        for side, count in categories['sup_syrnik']:
            syrniki_line += f" + {side}"
            if count > 1:
                syrniki_line += f" * {count}"
        dish_counter[syrniki_line] += 1

    return dish_counter


async def test_dish():
    dishes_list = [[{'dish': DishData(id=1550, name='Сосиска из индейки, 1 шт.', weight='60 г.', amount=26, compound='',
                                      image_url='https://domstolovaya.ru/upload/iblock/cfd/cfd814e7317a68ce8027b2d661e8f7d1.jpg',
                                      calories='95.3', group_id=191), 'count': 1}, {
                        'dish': DishData(id=1552, name='Сырник', weight='60 г.', amount=31,
                                         compound='творог, яйцо, мука, специи',
                                         image_url='https://domstolovaya.ru/upload/iblock/50a/50a337a4d86905e5bdd2b7a6a4ecc3dc.JPG',
                                         calories='218.5', group_id=191), 'count': 2}, {
                        'dish': DishData(id=1605, name='Мед', weight='20 г.', amount=11, compound='', image_url='',
                                         calories='65.8', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1606, name='Сгущенка', weight='20 г.', amount=14, compound='', image_url='',
                                         calories='65.9', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1694, name='Каша Дружба молочная', weight='200 г.', amount=30, compound='',
                                         image_url='', calories='304.8', group_id=191), 'count': 1}, {
                        'dish': DishData(id=1973, name='Сметана добавка', weight='30 г.', amount=10, compound='',
                                         image_url='', calories='61.2', group_id=197), 'count': 1}],
                   [{'dish': DishData(id=1552, name='Сырник', weight='60 г.', amount=31,
                                      compound='творог, яйцо, мука, специи',
                                      image_url='https://domstolovaya.ru/upload/iblock/50a/50a337a4d86905e5bdd2b7a6a4ecc3dc.JPG',
                                      calories='218.5', group_id=191), 'count': 1}, {'dish': DishData(id=1550, name='Сосиска из индейки, 1 шт.', weight='60 г.', amount=26, compound='',
                                      image_url='https://domstolovaya.ru/upload/iblock/cfd/cfd814e7317a68ce8027b2d661e8f7d1.jpg',
                                      calories='95.3', group_id=191), 'count': 2}, {
                        'dish': DishData(id=1557, name='Борщ с говядиной', weight='250 г.', amount=52, compound='',
                                         image_url='https://domstolovaya.ru/upload/iblock/d64/d641f187543a8fbe56b19fe0018ab792.jpg',
                                         calories='100.5', group_id=192), 'count': 1}, {
                        'dish': DishData(id=1597, name='Медово-горчичный соус', weight='40 г.', amount=15, compound='',
                                         image_url='', calories='0.0', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1599, name='Подлива', weight='40 г.', amount=7, compound='', image_url='',
                                         calories='16.6', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1601, name='Гренки', weight='10 г.', amount=5, compound='', image_url='',
                                         calories='36.9', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1602, name='Зелень', weight='3 г.', amount=4, compound='', image_url='',
                                         calories='1.4', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1604, name='Масло сливочное 82,5%', weight='10 г.', amount=10, compound='',
                                         image_url='', calories='74.4', group_id=197), 'count': 1}, {
                        'dish': DishData(id=1605, name='Мед', weight='20 г.', amount=11, compound='', image_url='',
                                         calories='65.8', group_id=197), 'count': 2}, {
                        'dish': DishData(id=1694, name='Каша Дружба молочная', weight='200 г.', amount=30, compound='',
                                         image_url='', calories='304.8', group_id=191), 'count': 1}, {
                        'dish': DishData(id=1973, name='Сметана добавка', weight='30 г.', amount=10, compound='',
                                         image_url='', calories='61.2', group_id=197), 'count': 2}]

                   ]
    result = defaultdict(int)
    for dishes in dishes_list:
        dishes_dict = await dishes_in_side_items(dishes)
        for key, value in dishes_dict.items():
            result[key] += value
    # print(result)
    result_lines = []
    for dish, count in result.items():
        result_lines.append(f"{dish} - {count}")

    print("\n".join(result_lines))

if __name__ == "__main__":
    asyncio.run(test_dish())
