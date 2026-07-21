"""
Example of a per-supplier custom module.

When a template folder contains a `.py` file next to its `.json`, the loader
imports it and attaches it to the template as `custom_module`. The parser then
calls `custom_fields()` after regex extraction, which is where you put logic
that regexes cannot express: derived values, date arithmetic, unit conversion,
supplier-specific quirks.
"""

import datetime

BOX_WEIGHT_KG = 25


def can_be_float(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def custom_fields(extracted_data: dict) -> dict:
    """Post-process the fields extracted for this supplier."""

    # 1. Normalise the date DD/MM/YYYY -> YYYYMMDD, and derive the expected
    #    arrival date (this supplier ships with a 5-day lead time).
    if extracted_data.get("INVOICE_DATE"):
        invoice_date = datetime.datetime.strptime(extracted_data["INVOICE_DATE"], "%d/%m/%Y")
        extracted_data["INVOICE_DATE"] = invoice_date.strftime("%Y%m%d")
        extracted_data["ARRIVAL_DATE"] = (invoice_date + datetime.timedelta(days=5)).strftime("%Y%m%d")

    # 2. Invoice numbers are printed without leading zeros — pad to 6 digits.
    if extracted_data.get("INVOICE_NUMBER"):
        extracted_data["INVOICE_NUMBER"] = str(extracted_data["INVOICE_NUMBER"]).zfill(6)

    # 3. Gross weight is not printed on this supplier's invoice; derive it.
    box_count = extracted_data.get("BOX_PLACES_COUNT")
    if box_count and can_be_float(box_count):
        extracted_data["GROSS_WEIGHT"] = BOX_WEIGHT_KG * float(box_count)

    return extracted_data
