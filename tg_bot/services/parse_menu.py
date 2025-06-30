from typing import Dict

import requests
from bs4 import BeautifulSoup
from requests import RequestException


def get_day_text_page(day: str):
    cookies = {
        'PHPSESSID': 'B0BW4VY6f0fsfN4IKQ02jDntpoYrfsYD',
    }

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'cache-control': 'max-age=0',
        # 'cookie': 'PHPSESSID=B0BW4VY6f0fsfN4IKQ02jDntpoYrfsYD',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    }

    params = {
        'day': day,
    }

    try:
        response = requests.get('https://domstolovaya.ru/menu/', params=params, cookies=cookies, headers=headers)
        if response:
            return response.text
    except RequestException as e:
        print(f"Ошибка при выполнении запроса: {e}")
    return False


def parse_page(html) -> Dict:
    soup = BeautifulSoup(html, 'html.parser')
    menu = {}

    # Проходим по всем категориям
    categories = soup.find_all('div', class_='assortment__title dishes')
    for category in categories:
        category_name = category.text.strip()  # Название категории
        menu[category_name] = {}  # Добавляем категорию в словарь

        # Получаем товары для данной категории
        section_id = category.get('data-section')
        items = soup.find_all('div', class_='assortment__item', attrs={'data-section': section_id})

        for item in items:
            # Название товара
            item_name = item.find('div', class_='assortment__item-title--name').text.strip() if item.find('div', class_='assortment__item-title--name') else ''
            if item_name is False:
                continue
            # Вес
            weight = item.find('div', class_='assortment__item-title--weight').text.strip() if item.find('div', class_='assortment__item-title--weight') else ''
            # try:
            #     if '/' in weight_text:
            #         weight_parts = weight_text.replace('г.', '').strip().split('/')
            #         weight = sum(float(part.strip()) for part in weight_parts) / len(weight_parts)
            #     else:
            #         weight = float(weight_text.replace('г.', '').strip())
            # except ValueError:
            #     weight = 0.0

            # Калории
            calories_text = item.find('div', class_='assortment__item-title--calories').text.strip() if item.find('div', class_='assortment__item-title--calories') else ''
            try:
                calories = float(calories_text.replace('ккал', '').strip().replace(',', '.'))
            except ValueError:
                calories = 0.0

            # Цена
            price_text = item.find('div', class_='assortment__item-title--price').text.strip() if item.find('div', class_='assortment__item-title--price') else ''
            try:
                price = float(price_text.replace('р.', '').strip())
            except ValueError:
                price = 0.0

            # Изображение
            image = item.find('div', class_='assortment__item-title--name').get('data-image', '').strip() if item.find('div', class_='assortment__item-title--name') else ''
            if image:
                image = "https://domstolovaya.ru"+image

            # Состав
            description = item.find('div', class_='assortment__item-title--name').get('data-text', '').strip() if item.find('div', class_='assortment__item-title--name') else ''
            composition = BeautifulSoup(description, 'html.parser').text if description else ''
            # if composition:
            #     composition = composition.replace("Состав:\r\n", "").replace("Состав:\xa0", "").replace("Состав: ", "")

            # Добавляем товар в категорию
            menu[category_name][item_name] = {
                'compound': composition,
                'weight': weight,
                'calories': calories,
                'price': price,
                'image': image
            }

    return menu


if __name__ == "__main__":
    day = "Понедельник"
    text = get_day_text_page(day)
    # parse_page(text)
    print(parse_page(text))
