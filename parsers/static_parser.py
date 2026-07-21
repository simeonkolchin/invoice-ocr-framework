from parsers import BaseParser
from core import InvoiceTemplate


class StaticParser(BaseParser):
    """Класс для парсинга полей с помощью Tesseract и регулярных выражений."""

    def parse(self, pdf_path, template: InvoiceTemplate):
        if "static" not in template.fields:
            return {}

        return template.fields["static"]
