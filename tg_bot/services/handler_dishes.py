from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from tg_bot.essence.dishes import DishData
from tg_bot.essence.groups import Group


async def dishes_in_side_items(dishes, session: AsyncSession):
    group_table = Group(session)
    groups = await group_table.get_all_groups()
    ids_groups = {group.id: group.name for group in groups}

    garnishes = []  # Гарниры
    mains = []  # Вторые блюда
    soups = []  # Первые блюда
    supplement_garnish = []  # Добавки для гарнира
    supplement_syrnik = []  # Добавки для сырников
    supplement_soup = []  # Добавки для супа
    syrniki_count = 0  # Количество сырников
    smetana_count = 0  # Кол-во сметаны
    dish_counter = defaultdict(int)  # Для подсчёта всех блюд

    for item in dishes:
        dish = item['dish']
        count = item['count']
        group_name = ids_groups.get(dish.group_id, '')
        # Проверка на группы и ключевые слова
        if 'каша' in dish.name.lower() or group_name == 'Гарниры':
            garnishes.append((dish.name, count))
        elif group_name == 'Вторые блюда':
            mains.append((dish.name, count))
        elif group_name == 'Первые блюда':
            soups.append((dish.name, count))
        elif group_name == 'Добавки':
            if 'сметана' in dish.name.lower().split():
                smetana_count += count
            elif dish.name.lower() in ['зелень', 'гренки']:
                supplement_soup.append((dish.name, count))
            elif dish.name.lower() in ['мед', 'сгущенка', 'мёд', 'сгущёнка']:
                supplement_syrnik.append((dish.name, count))
            else:
                supplement_garnish.append((dish.name, count))
        elif 'сосиска' in dish.name.lower() or 'купаты' in dish.name.lower():
            mains.append((dish.name, count))
        elif "сгущенка" in dish.name.lower():
            supplement_syrnik.append((dish.name, count))
        elif dish.name.lower() == 'сырник':
            syrniki_count += count
        else:
            dish_counter[dish.name] += count

    # Обработка супов с добавками
    for soup, soup_count in soups:
        combined_sides = [side for side, side_count in supplement_soup if side_count > 0]
        for i in range(soup_count):
            text = f"{soup}"
            if "борщ" in soup.lower().split() and smetana_count > 0:
                text += f" + Сметана"
                smetana_count -= 1
            if combined_sides and supplement_soup:
                text += f" + {' + '.join(combined_sides)}"
                supplement_soup.clear()
            dish_counter[text] += 1

    # Обработка гарниров с добавками
    for garnish, garnish_count in garnishes:
        combined_sides = [side for side, side_count in supplement_garnish if side_count > 0]
        for i in range(garnish_count):
            text = f"{garnish}"
            if mains:
                for main, mains_count in mains:
                    text += f" + {main}"
                    if mains_count > 1:
                        text += f" * {mains_count}"
                    mains.remove((main, mains_count))
            if combined_sides and supplement_garnish:
                text += f" + {' + '.join(combined_sides)}"
                supplement_garnish.clear()
            dish_counter[text] += 1

    # Добавление оставшихся главных блюд отдельно
    for main, main_count in mains:
        if main_count > 0:
            dish_counter[main] += main_count

    # Сырники + Сметана + Сгущенка объединяются
    if syrniki_count > 0:
        syrniki_line = "Сырник" if syrniki_count == 1 else f"{syrniki_count} Сырника"
        if smetana_count > 0:
            syrniki_line += f" + Сметана"
            if smetana_count > 1:
                syrniki_line += f" * {smetana_count}"
            smetana_count = 0
        for side, count in supplement_syrnik:
            syrniki_line += f" + {side}"
            if count > 1:
                syrniki_line += f" * {count}"
            supplement_syrnik.remove((side, count))
        dish_counter[syrniki_line] += 1
    if smetana_count > 0:
        dish_counter["Сметана"] += smetana_count
    for supplement, count in supplement_syrnik:
        dish_counter[supplement] += count
    return dish_counter


if __name__ == "__main__":
    pass
