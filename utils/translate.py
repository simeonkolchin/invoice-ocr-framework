"""
Reference dictionaries used to normalise and translate values read by OCR.

`InvoiceParser` looks a value up here first; if it is not found exactly, it
retries with a Levenshtein distance of 1, which repairs the single-character
mistakes OCR typically makes on scanned invoices ("FREEDOM" -> "FREEOOM").

In a real deployment these dictionaries are large (thousands of product names
and consignee markings). The sample below is intentionally small and synthetic
— it only demonstrates the mechanism.
"""

# Product names as they appear on the invoice  ->  canonical / localised name
translate_dict = {
    "FREEDOM": "ФРИДОМ",
    "EXPLORER": "ЭКСПЛОРЕР",
    "MONDIAL": "МОНДИАЛЬ",
    "VENDELA": "ВЕНДЕЛА",
    "PINK FLOYD": "ПИНК ФЛОЙД",
    "HIGH MAGIC": "ХАЙ МЭДЖИК",
    "DEEP PURPLE": "ДИП ПЁПЛ",
    "WHITE NAOMI": "ВАЙТ НАОМИ",
    "RED PARIS": "РЕД ПАРИЖ",
    "SWEET AKITO": "СВИТ АКИТО",
    "GYPSOPHILA": "ГИПСОФИЛА",
    "EUCALYPTUS": "ЭВКАЛИПТ",
    "ALSTROEMERIA": "АЛЬСТРОМЕРИЯ",
    "CHRYSANTHEMUM": "ХРИЗАНТЕМА",
    "CARNATION": "ГВОЗДИКА",
}

# Consignee / marking strings  ->  normalised form
marking_dict = {
    "NORTHWIND TRADING": "НОРТВИНД ТРЕЙДИНГ",
    "MERIDIAN IMPORT": "МЕРИДИАН ИМПОРТ",
    "BLUEHARBOR LLC": "БЛЮХАРБОР",
    "SAMPLE CONSIGNEE": "ОБРАЗЕЦ ПОЛУЧАТЕЛЯ",
}
