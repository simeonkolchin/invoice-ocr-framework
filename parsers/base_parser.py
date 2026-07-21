class BaseParser:
    """Базовый класс для всех парсеров."""

    def parse(self, text, template):
        raise NotImplementedError("Метод parse должен быть реализован в подклассе")
