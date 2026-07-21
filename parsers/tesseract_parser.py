from parsers.base_parser import BaseParser
import re
from pdf2image import convert_from_path
import easyocr
import numpy as np
import matplotlib.pyplot as plt


class TesseractParser(BaseParser):
    """Класс для парсинга полей с помощью Tesseract и регулярных выражений."""

    def __init__(self):
        super().__init__()
        self.ocr = easyocr.Reader(['en'])

    def parse_image_to_text(self, image):
        result = self.ocr.readtext(np.asarray(image))
        # Объединение всего текста с сохранением переносов строк
        text = "\n".join([detection[1] for detection in result]) if result else ""
        return text

    def parse(self, pdf_path, template):
        extracted_data = {}

        # Конвертируем PDF в изображения
        images = convert_from_path(pdf_path)
        
        # Обрабатываем каждую страницу
        all_text = []
        for image in images:
            page_text = self.parse_image_to_text(image)
            all_text.append(page_text)
        
        # Объединяем текст всех страниц с двойным переносом между страницами
        text = "\n\n".join(all_text)

        # Сохраняем извлеченный текст для отладки
        open("text.txt", "w", encoding='utf-8').write(text)

        # Извлекаем данные с помощью регулярных выражений
        for field_name, regex_pattern in template.fields.get("tesseract", {}).items():
            match = re.search(regex_pattern, text, re.IGNORECASE)
            if match:
                extracted_data[field_name] = match.group(1)

        return extracted_data
