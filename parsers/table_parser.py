from parsers.base_parser import BaseParser
from core import InvoiceTemplate
import pdfplumber


def extract_tables_separately(pdf_path):
    separate_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table_number, table in enumerate(tables, start=1):
                separate_tables.append({"page": page_number, "table_number": table_number, "data": table})
    return separate_tables


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


def find_matching_table_pattern(row, table_patterns):
    """
    Находит, какой из предопределённых шаблонов таблиц соответствует текущей строке.

    Аргументы:
    row (list): Строка для проверки по шаблонам.

    Возвращает:
    int или None: Индекс совпадающего шаблона или None, если ни один шаблон не совпадает.
    """
    for pattern_index, pattern in enumerate(table_patterns):
        if validate_column_names(row, pattern["columns"]):
            return pattern_index
    return None


class TableParser(BaseParser):
    """Класс для парсинга таблиц."""

    def parse(self, pdf_path, template: InvoiceTemplate):
        extracted_data = {"tables": [], "fields": {}}

        if "table" not in template.fields or len(template.fields["table"]) == 0:
            return extracted_data

        extracted_tables = extract_tables_separately(pdf_path)
        table_patterns = template.fields["table"]

        for table_data in extracted_tables:
            main_table_data = table_data["data"]

            current_table = {"table_name": None, "table_data": []}

            # Обрабатываем каждую строку данных основной таблицы, чтобы идентифицировать и организовать таблицы
            for row_index, row in enumerate(main_table_data):
                # Проверяем, содержит ли строка хотя бы одну непустую ячейку
                if any(cell for cell in row if cell is not None):
                    matching_pattern_index = find_matching_table_pattern(row, table_patterns)

                    if matching_pattern_index is not None:  # Если найден подходящий шаблон таблицы
                        if row_index != 0:  # Сохраняем предыдущие данные таблицы перед началом новой
                            extracted_data["tables"].append(current_table)
                            current_table = {"table_name": None, "table_data": []}

                        print(table_patterns[matching_pattern_index])
                        print(current_table)

                        current_table["table_name"] = table_patterns[matching_pattern_index]["name"]
                        current_table["table_data"].append(table_patterns[matching_pattern_index]["columns"])
                    else:
                        # Добавляем непустые ячейки в текущую таблицу
                        filtered_row_data = [cell for cell in row if cell is not None and len(cell)]
                        current_table["table_data"].append(filtered_row_data)

            # Добавляем последние данные таблицы
            extracted_data["tables"].append(current_table)

        # TODO: Здесь парситься вся таблица, а нам нужно будет парсить определенные ячейки.
        # Нужно будет в шаблон добавить возможно парсить определенные таблицы, пишите как считаете правильным

        return extracted_data
