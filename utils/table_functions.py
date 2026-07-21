from pdf2image import convert_from_path
import pdfplumber
from typing import Dict
import cv2
import numpy as np
from core import InvoiceTemplate
from pytesseract import image_to_string, image_to_data
from re import match
import pytesseract
from PIL import Image


def extract_tables_separately(pdf_path):
    separate_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table_number, table in enumerate(tables, start=1):
                separate_tables.append({"page": page_number, "table_number": table_number, "data": table})
    return separate_tables


def preprocess_image(image):
    # Конвертация изображения в массив NumPy для предобработки
    image_np = np.array(image)

    # Конвертируем в оттенки серого
    gray_image = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)

    # Применяем пороговую бинаризацию
    _, binary_image = cv2.threshold(gray_image, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Увеличение контраста
    contrast_image = cv2.convertScaleAbs(binary_image, alpha=1.5, beta=0)

    # Возвращаем изображение как PIL-объект обратно
    return contrast_image


def validate_column_names(row, expected_columns):
    """
    Проверяет, содержит ли строка валидные имена столбцов из ожидаемого списка.

    Аргументы:
    row (list): Строка для проверки.
    expected_columns (list): Список валидных имён столбцов.

    Возвращает:
    bool: True, если все имена в строке валидные, иначе False.
    """
    for cell in row:
        if cell is not None and len(cell) > 0 and cell not in expected_columns:
            return False
    return True


def validate_column_names_void_fix(row, expected_columns):
    """
    Упрощенная функция проверки столбца с шапкой таблицы из шаблона

    Аргументы:
    row (list): Строка для проверки.
    expected_columns (list): Список валидных имён столбцов.

    Возвращает:
    bool: True, если размеры двух списков совпадают, иначе False.
    """

    if len(row) != len(expected_columns):
        return False
    return True


def find_matching_table_pattern(row, table_patterns, void_fix=False):
    """
    Находит, какой из предопределённых шаблонов таблиц соответствует текущей строке.

    Аргументы:
    row (list): Строка для проверки по шаблонам.

    Возвращает:
    int или None: Индекс совпадающего шаблона или None, если ни один шаблон не совпадает.
    """
    for pattern_index, pattern in enumerate(table_patterns):
        # Если используем обработку таблицы без удаления пустых ячеек используем функцию с void_fix
        if void_fix:
            if validate_column_names_void_fix(row, pattern["columns"]):
                return pattern_index
        else:
            if validate_column_names(row, pattern["columns"]):
                return pattern_index
    return None


def main_get_tables(pdf_path: str, template_fields: Dict):
    extracted_data = dict()

    # ОСНОВНАЯ ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ТАБЛИЦ
    # поверх неё будем писать обработчик нужных таблиц

    if "table" not in template_fields or len(template_fields["table"]) == 0:
        return extracted_data

    extracted_tables = extract_tables_separately(pdf_path)
    # return extracted_tables
    table_patterns = template_fields["table"]

    for table_data in extracted_tables:
        main_table_data = table_data["data"]

        current_table = {"name": None, "data": []}

        for row_index, row in enumerate(main_table_data):
            # Проверяем, содержит ли строка хотя бы одну непустую ячейку
            if any(cell for cell in row if cell is not None):
                matching_pattern_index = find_matching_table_pattern(row, table_patterns)

                if matching_pattern_index is not None:  # Если найден подходящий шаблон таблицы
                    if row_index != 0:  # Сохраняем предыдущие данные таблицы перед началом новой
                        extracted_data[current_table["name"]] = current_table["data"]
                        current_table = {"name": None, "data": []}

                    current_table["name"] = table_patterns[matching_pattern_index]["name"]
                    current_table["data"].append(table_patterns[matching_pattern_index]["columns"])
                else:

                    # Добавляем непустые ячейки в текущую таблицу
                    filtered_row_data = [cell for cell in row if cell is not None and len(cell)]
                    current_table["data"].append(filtered_row_data)

        extracted_data[current_table["name"]] = current_table["data"]

    return extracted_data


def main_get_tables_void_fix(pdf_path: str, template_fields: Dict):
    """
    В этой функции шапка таблицы подбирается по критерию совпадения числа столбцов.
    Поэтому внутри шаблона <invoice>.json НЕ ДОЛЖНО БЫТЬ 2 таблиц с одинаковым числом столбцов
    """

    extracted_data = dict()
    table_patterns = template_fields["table"]

    if "table" not in template_fields or len(template_fields["table"]) == 0:
        return extracted_data

    extracted_tables = extract_tables_separately(pdf_path)

    # Проход по всех спаршенным из pdf таблицам
    for table_data in extracted_tables:
        main_table_data = table_data["data"]

        current_table = {"name": None, "data": []}

        # Проход по строкам таблицы
        for row_index, row in enumerate(main_table_data):
            # Проверяем, содержит ли строка хотя бы одну непустую ячейку
            if any(cell for cell in row if cell is not None):
                matching_pattern_index = find_matching_table_pattern(row, table_patterns, True)

                if matching_pattern_index is not None:  # Если найден подходящий шаблон таблицы
                    if row_index == 0:
                        table_name = table_patterns[matching_pattern_index]["name"]
                        current_table["name"] = table_name

                    current_table["data"].append(row)

        # пропускает создание новой таблицы если её имя "None"
        if current_table["name"] is None:
            continue
        # создает новую таблицу, если её не было раньше, и расширяет старую, если она нашлась
        if current_table["name"] not in extracted_data:
            if current_table["data"][0] != table_patterns[matching_pattern_index]["columns"]:
                current_table["data"].insert(0, table_patterns[matching_pattern_index]["columns"])
            extracted_data[current_table["name"]] = current_table["data"]
        else:
            extracted_data[current_table["name"]].extend(current_table["data"])
    return extracted_data


def main_get_from_non_table(pdf_path, template: InvoiceTemplate):
    # Конвертируем PDF в изображения
    images = convert_from_path(pdf_path)
    all_rows = ""

    for image in images:
        width, height = image.size
        # Обрезаем изображение до области нижней таблицы
        bottom_table_part = image.crop((0, int(height * template["non_table"]["split_coordinates"][0]), width, height))

        # Применяем предобработку изображения для улучшения качества OCR
        preprocessed_image = preprocess_image(bottom_table_part)

        # Преобразуем обратно в PIL для работы с pytesseract
        text = image_to_string(preprocessed_image, config="--psm 6")

        # text = image_to_string(bottom_table_part)

        # Удаляем пустые строки
        lines = text.splitlines()
        rows = [line for line in lines if line.strip()]

        all_rows = "\n".join(rows[2::])
    # open('text.txt', 'w', encoding='utf-8').write(all_rows)

    return all_rows


def get_small_table(pdf_path, template: InvoiceTemplate):
    images = convert_from_path(pdf_path)

    rows = []
    for idx, image in enumerate(images):
        width, height = image.size
        # Обрезаем изображение до нашей таблички
        table_small = image.crop(
            (
                int(height * template["small_table"]["split_horizontal_left"]),
                int(height * template["small_table"]["split_vertical_up"]),
                int(height * template["small_table"]["split_horizontal_right"]),
                int(height * template["small_table"]["split_vertical_down"]),
            )
        )

        width, height = table_small.size

        # table_small = preprocess_image(table_small)
        # plt.imshow(table_small)
        # plt.show()

        # Используем pytesseract для извлечения данных с координатами
        data = image_to_data(table_small, config="--psm 6", output_type=pytesseract.Output.DATAFRAME)

        # Оставляем только строки с валидным текстом (conf > 0)
        data = data[(data["conf"] > 0)]

        # Перебираем строки для получения текста и координат
        extracted_data = []
        for i, row in data.iterrows():
            text = row["text"].strip()
            text = text.replace(",", ".")

            # Если плохо спарсилось число с плавающей точкой
            if match(r"^\d+$", text) and text[0] == "0":
                text = "0" + "." + text[1::]

            if match(r"^\d+(\.\d+)?$", text):
                extracted_data.append(
                    {
                        "text": text,  # Извлеченный текст
                        "left": row["left"],  # Координата X (начало блока по горизонтали)
                        "top": row["top"],  # Координата Y (начало блока по вертикали)
                        "width": row["width"],  # Ширина блока
                        "height": row["height"],  # Высота блока
                    }
                )

        # Сортировка по высоте (top), затем по ширине (left)
        extracted_data = sorted(extracted_data, key=lambda x: (x["top"], x["left"]))

        width_columns = [(extracted_data[0]["left"] - 5, extracted_data[1]["left"] + 5)]
        r = width_columns[0][1] - width_columns[0][0]
        next = 50
        for i in range(2, 13, 2):
            width_columns.append((width_columns[i // 2 - 1][1] + next, width_columns[i // 2 - 1][1] + next + r))

        # Формирование строк
        row = []
        column = 0
        previous_top = extracted_data[0]["top"]
        cnt = 0
        for r in extracted_data:
            if previous_top != r["top"]:
                previous_top = r["top"]
                break
            cnt += 1

        for i in range(cnt, len(extracted_data)):
            if extracted_data[i]["top"] != previous_top:
                for _ in range(column, 12):
                    row.append("0")
                rows.append(row)
                row = []
                column = 0
            while column != 12 and extracted_data[i]["left"] > width_columns[column // 2][1]:
                column += 2
                row += ["0", "0"]
            if column == 12:
                print("Ошибка в размерах: small_table")
                return
            row.append(extracted_data[i]["text"])
            column += 1
            previous_top = extracted_data[i]["top"]

        for _ in range(column, 12):
            row.append("0")
        rows.append(row)

        # Записываем результат в JSON-файл
        # with open("text.json", 'w', encoding='utf-8') as f:
        #     json.dump(rows, f, ensure_ascii=False, indent=4)
    return rows
