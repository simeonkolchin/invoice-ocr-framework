from parsers.base_parser import BaseParser
import re
from pdf2image import convert_from_path
from core import InvoiceTemplate
import easyocr
import numpy as np


def remove_empty_lines(text):
    # Разбиваем текст на строки и оставляем только непустые строки
    lines = text.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]

    # Соединяем непустые строки обратно в один текст
    return "\n".join(non_empty_lines)


WHITE_THRESHOLD = (240, 240, 240)


def find_right_non_white_pixel(image):
    image = image.convert("RGB")
    width, height = image.size

    for x in range(width - 1, -1, -1):
        for y in range(height):
            pixel = image.getpixel((x, y))
            if pixel < WHITE_THRESHOLD:
                return x
    return width


def crop_image_by_right_non_white(image):
    width, height = image.size

    print(height, width)

    if height > width:
        return image

    right_edge = find_right_non_white_pixel(image)
    cropped_image = image.crop((0, 0, right_edge, image.height))
    return cropped_image


class TesseractSplitParser(BaseParser):
    """Класс для парсинга полей с помощью Tesseract и регулярных выражений."""

    def __init__(self):
        super().__init__()
        # Инициализация EasyOCR
        self.ocr = easyocr.Reader(['en'])

    def parse_image_to_text(self, image):
        result = self.ocr.readtext(np.asarray(image))
        # Объединение всего текста с сохранением переносов строк
        text = "\n".join([detection[1] for detection in result]) if result else ""
        return text

    # Здесь мы делим изображение на 2 части потому что так раделена таблица, и чтобы не писать сложные регулярки проще сделать так:)
    # Хотя возможно обойтись и без этого модуля, в конец регулярки нужно будет запихнуть следующее слово справа, но мы так не сделали:)
    def parse(self, pdf_path, template: InvoiceTemplate):
        extracted_data = {}

        # Конвертируем PDF в изображения
        # origin_images = convert_from_path(pdf_path, poppler_path=r'C:\\Users\\timof\\Downloads\\poppler\\poppler-24.08.0\\Library\\bin')
        origin_images = convert_from_path(pdf_path)
        images = [crop_image_by_right_non_white(image) for image in origin_images]

        for image in images:
            width, height = image.size

            # Переменная для объединенного со всех частей текста
            combined_text = ""

            # Определяем координаты для левой части
            left_part = image.crop((0, 0, int(width * float(template.split_coordinates[0])), height))
            left_text = self.parse_image_to_text(left_part)
            # left_text = pytesseract.image_to_string(left_part, config="-l eng --oem 1")
            combined_text += left_text

            # plt.imshow(left_part)
            # plt.show()

            # Если разделителей больше одного, то работаем со всеми серединными частями
            if len(template.split_coordinates) != 1:
                for split_index in range(len(template.split_coordinates) - 1):
                    middle_part = image.crop(
                        (
                            int(width * template.split_coordinates[split_index]),
                            0,
                            int(width * template.split_coordinates[split_index + 1]),
                            height,
                        )
                    )
                    middle_text = self.parse_image_to_text(middle_part)
                    combined_text += "\n" + middle_text

            # Определяем координаты для правой части
            right_part = image.crop((int(width * template.split_coordinates[-1]), 0, width, height))
            right_text = self.parse_image_to_text(right_part)
            combined_text += "\n" + right_text

            # plt.imshow(right_part)
            # plt.show()

            combined_text = remove_empty_lines(combined_text)

            # open(f'text_split_{pdf_path.split("/")[-1][:-4]}.txt', 'w', encoding='utf-8').write(combined_text)

            # Применяем регулярные выражения к объединенному тексту
            for field_name, regex_pattern in template.fields.get("tesseract_split").items():
                if field_name != "split_coordinates":  # Пропускаем поле разделения
                    match = re.search(regex_pattern, combined_text)
                    if match:
                        extracted_data[field_name] = match.group(1)
                    else:
                        print(f"REGEX_PATTERN: {regex_pattern}")

                        # print(regex_pattern)
                        # print(match)

        return extracted_data
