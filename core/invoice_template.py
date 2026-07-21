from typing import Dict, List


class InvoiceTemplate:
    def __init__(self, name, keywords, fields, split_coordinates, non_fields, custom_module=None):
        self.name: str = name
        self.keywords: List = keywords
        self.fields: Dict = fields
        self.split_coordinates: List[float] = split_coordinates
        self.non_fields: List[str] = non_fields
        self.custom_module = custom_module

    def match(self, text: str) -> bool:
        # Проверяем, содержит ли текст ключевые слова из шаблона
        return any(keyword.lower() in text.lower() for keyword in self.keywords)
