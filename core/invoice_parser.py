import pytesseract
from pdf2image import convert_from_path
from parsers import TesseractParser, TesseractSplitParser, StaticParser
from core import InvoiceTemplate
from utils.translate import translate_dict, marking_dict
import re
from typing import List
from Levenshtein import distance
import matplotlib.pyplot as plt


# pytesseract.pytesseract.tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'


def get_corrected_name(name, translate_dict, typ="translate"):
    if name in translate_dict:
        return translate_dict[name]

    # Если имя точно в значениях, возвращаем None (имя не найдено)
    if name in translate_dict.values():
        return name

    for key in translate_dict.keys():
        if distance(name, key) == 1:  # Ищем ровно одно изменение
            print(f"{name} -> {key} -> {translate_dict[key]}")
            return translate_dict[key]

    print(f"НАЗВАНИЯ '{name}' НЕ УДАЛОСЬ НАЙТИ В {typ}_dict")
    return name


class InvoiceParser:
    def __init__(self, templates: List[InvoiceTemplate]):
        self.templates = templates
        # Создаем словарь парсеров, сопоставляющий типы парсинга с экземплярами парсеров
        self.parsers = {
            "tesseract": TesseractParser(),
            # 'table': TableParser(),
            "tesseract_split": TesseractSplitParser(),
            "static": StaticParser(),
        }

    def parse_pdf(self, pdf_path):
        # Извлекаем текст с первой страницы PDF с использованием Tesseract
        # first_page_image = convert_from_path(pdf_path, first_page=0, last_page=1, poppler_path=r'C:\\Users\\timof\\Downloads\\poppler\\poppler-24.08.0\\Library\\bin')[0]
        first_page_image = convert_from_path(pdf_path, first_page=0, last_page=1)[0]
        text = pytesseract.image_to_string(first_page_image, config="-l eng --oem 1")

        # Ищем подходящий шаблон
        for template in self.templates:
            if template.match(text):
                # Если нашли подходящий шаблон: парсим pdfку при помощи данного шаблона
                return self.extract_fields(pdf_path, template)
        return None

    def fill_values(self, extracted_data, template: InvoiceTemplate):

        empty_dict = {
            "INVOICE_NUMBER": "0000000",
            "AVIA_TICKET": "000-0000-0000",
            "ROSE_WEIGHT": -1.0,
            "ALSTROMETRIA_WEIGHT": -1,
            "FULL_PLACES_COUNT": 0.0,
            "BOX_PLACES_COUNT": 0.0,
            "QB_BOX_PLACES_COUNT": 0,
            "AMS_DATA": "00000000",
            "MSK_DATA": "00000000",
            "AWB_CONTRAGENT": "Не найдено",
            "AWB_BID": 0,
            "PRICOOL_CONTRAGENT": "Не найдено",
            "TRACK": 0,
            "TRANSPORT_COMPANY": 0,
            "MARKING/NOTIFY": "Не найдено",
            "CONTRAGENT": 0,
            "PRODUCTS": [],
        }

        for column in empty_dict:
            if column not in extracted_data:
                extracted_data[column] = empty_dict[column]
                print(f'Беда, нет колонки "{column}"')

        if "MARKING/NOTIFY" in extracted_data and extracted_data["MARKING/NOTIFY"] in marking_dict:
            extracted_data["MARKING/NOTIFY"] = marking_dict[extracted_data["MARKING/NOTIFY"]]
        elif "MARKING/NOTIFY" in extracted_data:
            cur_marking = extracted_data["MARKING/NOTIFY"]
            if cur_marking.endswith("."):
                cur_marking = cur_marking[:-1]

            if cur_marking in marking_dict:
                extracted_data["MARKING/NOTIFY"] = cur_marking
            else:
                extracted_data["MARKING/NOTIFY"] = get_corrected_name(cur_marking, marking_dict, typ="marking")
            print(f'MARKING: {extracted_data["MARKING/NOTIFY"]} не был найден')

        for i in range(len(extracted_data["PRODUCTS"])):
            name = extracted_data["PRODUCTS"][i]["name"].replace("!", "").strip().upper()
            extracted_data["PRODUCTS"][i]["name"] = get_corrected_name(name, translate_dict)

        if "AVIA_TICKET" in extracted_data:
            ticket_number = re.sub(r"\s+|-", "", extracted_data["AVIA_TICKET"])
            extracted_data["AVIA_TICKET"] = f"{ticket_number[:3]}-{ticket_number[3:7]}-{ticket_number[7:]}"

        return extracted_data

    def extract_fields(self, pdf_path, template: InvoiceTemplate):
        extracted_data = {
            "name": template.name,
        }

        # Проходим по каждому типу полей в шаблоне
        for field_type, parser in self.parsers.items():
            if field_type in template.fields:
                # Используем соответствующий парсер для обработки полей данного типа
                parser_data = parser.parse(pdf_path, template)
                extracted_data.update(parser_data)

        for non_field in template.non_fields:
            extracted_data[non_field] = 0

        # Здесь запускается код из папки с инвойсом, чтобы обработать таблицу и какие то кастомные изменения
        if (
            template.custom_module is not None
            and hasattr(template.custom_module, "parse_table")
            and hasattr(template.custom_module, "custom_fields")
        ):
            module = template.custom_module

            table_summary = module.parse_table(pdf_path, template.fields)
            extracted_data = module.custom_fields(extracted_data)
            extracted_data["PRODUCTS"] = table_summary

        result = self.fill_values(extracted_data, template)

        return result
