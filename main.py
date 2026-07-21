"""
Entry point — parse a single invoice PDF with the template engine.

    python main.py path/to/invoice.pdf

For the continuous email-driven mode see `utils/utils.py`
(`process_new_emails`), which polls a mailbox and runs this same pipeline on
every new attachment. All credentials come from environment variables —
nothing is hard-coded.
"""

import json
import os
import sys

from core import InvoiceParser
from utils.utils import load_templates

TEMPLATE_DIR = os.environ.get("TEMPLATE_DIR", "templates")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]

    templates = load_templates(TEMPLATE_DIR)
    print(f"Loaded {len(templates)} template(s) from '{TEMPLATE_DIR}'")

    parser = InvoiceParser(templates)
    result = parser.parse_pdf(pdf_path)

    if result is None:
        print("No template matched this invoice — add one under templates/")
        sys.exit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
