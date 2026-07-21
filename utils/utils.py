import os
import email
import json
import re
import logging
import random
from core import InvoiceTemplate, InvoiceParser

import importlib.util
from imapclient import IMAPClient
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import xml.etree.ElementTree as ET
from xml.dom import minidom
from email.header import decode_header

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Укажите путь к вашему JSON-файлу с учетными данными
CLIENT_SECRET_FILE = os.environ.get("GOOGLE_CLIENT_SECRET_FILE", "config/client.json")
TOKEN_FILE = os.environ.get("GOOGLE_TOKEN_FILE", "config/token.json")
SCOPES = ["https://mail.google.com/", "https://www.googleapis.com/auth/drive.file"]

# Настройка логгера
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s – %(name)s | %(message)s", handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("global_logger")


def authenticate_google():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Сохранение токена
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return creds


def connect_to_gmail(creds, email):
    client = IMAPClient("imap.gmail.com", ssl=True)
    client.oauth2_login(email, creds.token)
    return client


def connect_to_drive(creds):
    return build("drive", "v3", credentials=creds)


def upload_file_to_drive(drive, file_path, drive_folder_id=None):
    """Загрузка файла на Google диск"""
    file_metadata = {"name": os.path.basename(file_path)}
    if drive_folder_id:
        file_metadata["parents"] = [drive_folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    drive.files().create(body=file_metadata, media_body=media, fields="id").execute()
    logging.info(f'"{os.path.basename(file_path)}" успешно загружен на Google диск\n')


def load_templates(template_dir: str) -> list[InvoiceTemplate]:
    """
    Загружает шаблоны из папки

    Аргументы:
    template_dir (str): Путь к папке с шаблонами.

    Возвращает:
    list[InvoiceTemplate]: Список объектов InvoiceTemplate, созданных из JSON-шаблонов.
    """

    templates = []
    for root in os.listdir(template_dir):
        # Пропуск файлов в корне папки <template_dir>
        full_root_path = os.path.join(template_dir, root)
        if not os.path.isdir(full_root_path):
            continue
        # Проход по всем файлам в папке шаблона
        for filename in os.listdir(full_root_path):
            # Чтение файла JSON из папки с шаблоном
            if filename.endswith(".json") and filename != "output.json":
                py_filename = filename.replace(".json", ".py")
                py_file_path = os.path.join(full_root_path, py_filename)

                # print(os.listdir(os.path.join(template_dir, root)), filename.replace('.json', '.py'))
                if os.path.exists(os.path.join(template_dir, root, filename.replace(".json", ".py"))):
                    spec = importlib.util.spec_from_file_location(
                        location=os.path.join(template_dir, root, filename.replace(".json", ".py")),
                        name=filename.replace(".json", ".py"),
                    )

                if os.path.exists(py_file_path):
                    spec = importlib.util.spec_from_file_location(py_filename, py_file_path)
                    custom_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(custom_module)
                else:
                    custom_module = None

                with open(os.path.join(full_root_path, filename), "r", encoding="utf-8") as file:
                    data = json.load(file)

                    if "table" in data["fields"]:
                        for i in range(len(data["fields"]["table"])):
                            for j in range(len(data["fields"]["table"][i]["columns"])):
                                if isinstance(data["fields"]["table"][i]["columns"][j], str):
                                    data["fields"]["table"][i]["columns"][j] = data["fields"]["table"][i]["columns"][
                                        j
                                    ].replace("\\n", "\n")

                    # Чтение шаблона из JSON в объект InvoiceTemplate
                    split_coordinates = data.get("split_coordinates", None)
                    template = InvoiceTemplate(
                        name=data["name"],
                        keywords=data["keywords"],
                        fields=data["fields"],
                        split_coordinates=split_coordinates,
                        non_fields=data["non_fields"],
                        custom_module=custom_module,
                    )
                    templates.append(template)

    return templates


def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*\r\n]', "_", filename)


def clean_xml_content(content):
    """Функция для удаления или замены нелегальных XML символов и последовательностей"""
    cleaned_content = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\x85\xA0-\uD7FF\uE000-\uFFFD]", " ", content)
    return cleaned_content


def correct_marking_notify(content):
    """Функция для исправления некорректного тега <MARKING/NOTIFY>"""
    corrected_content = content.replace("<MARKING/NOTIFY>", '<key name="MARKING/NOTIFY"').replace(
        "</MARKING/NOTIFY>", "</key>"
    )
    return corrected_content


def prettify_xml(elem):
    """Функция для форматирования XML с отступами"""
    rough_string = ET.tostring(elem, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="\t")


def determine_type(value):
    """Определение типа данных для XML-атрибута type"""
    if isinstance(value, str):
        return "str"
    elif isinstance(value, int):
        return "int"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, bool):
        return "bool"
    elif isinstance(value, list):
        return "list"
    elif isinstance(value, dict):
        return "dict"
    else:
        return "unknown"


def build_xml(element, data):
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ["tesseract", "tesseract_split"]:
                continue  # Пропускаем эти ключи
            # Проверка наличия недопустимых символов в ключе
            if re.search(r"[^a-zA-Z0-9_]", key):
                sub_element = ET.SubElement(element, "key", name=key)
            else:
                sub_element = ET.SubElement(element, key)
            sub_element.set("type", determine_type(value))
            build_xml(sub_element, value)
    elif isinstance(data, list):
        element.set("type", "list")
        for item in data:
            sub_element = ET.SubElement(element, "item")  # Изменяем "Item" на "item"
            sub_element.set("type", "dict")  # Указываем, что item — это dict
            build_xml(sub_element, item)
    else:
        element.text = str(data)
        element.set("type", determine_type(data))


def parse_and_save_pdf(pdf_path, output_folder):
    templates = load_templates("code/invoices")
    parser = InvoiceParser(templates=templates)
    result = parser.parse_pdf(pdf_path)

    if result is None:
        logger.info(f"Не удалось обработать инвойс {pdf_path}")
        return None

    # Преобразование JSON в XML
    root = ET.Element("root")
    build_xml(root, result)

    # Приведение XML к строке
    rough_string = ET.tostring(root, "utf-8")

    # Преобразуем строку в текст и применяем функции форматирования
    content = rough_string.decode("utf-8")
    content = clean_xml_content(content)
    content = correct_marking_notify(content)

    # Парсим отформатированный контент снова в XML элемент
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        logging.info(f"Ошибка парсинга при форматировании файла: {pdf_path}: {e}")
        return

    # Применяем красивое форматирование
    pretty_xml = prettify_xml(root)

    # Сохранение отформатированного XML в файл
    xml_filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".xml"
    xml_path = os.path.join(output_folder, xml_filename)
    with open(xml_path, "w", encoding="utf-8") as file:
        file.write(pretty_xml)

    logging.info(f'"{os.path.basename(xml_path)}" сохранен в xml')
    return xml_path


def decode_filename(encoded_filename):
    decoded_bytes, charset = decode_header(encoded_filename)[0]
    if charset is not None:
        decoded_filename = decoded_bytes.decode(charset)
    else:
        decoded_filename = decoded_bytes
    return decoded_filename


def process_new_emails(client, drive, drive_folder_id):
    client.select_folder("Inbox")
    messages = client.search(["UNSEEN"])
    temp_files_folder = "temp"

    for msg_id in messages:
        logging.info(f"Обработка Email {msg_id}")
        raw_message = client.fetch(msg_id, ["RFC822"])[msg_id][b"RFC822"]
        msg = email.message_from_bytes(raw_message)

        if msg.is_multipart():
            for part in msg.walk():
                content_disposition = str(part.get("Content-Disposition"))
                if "attachment" in content_disposition:
                    encoded_filename = part.get_filename()
                    if encoded_filename:
                        # Декодируем имя файла
                        filename = sanitize_filename(decode_filename(encoded_filename))
                        filepath = os.path.join(temp_files_folder, filename)

                        # Проверяем, что содержимое не None
                        payload = part.get_payload(decode=True)
                        if payload is not None:
                            with open(filepath, "wb") as f:
                                f.write(payload)
                                logging.info(f'"{filename}" скачан из письма')
                        else:
                            logging.warning(f"Часть письма не имеет содержимого: {filename}")
        
        logging.info(f"Email {msg_id} обработан\n\n\n")

    files = os.listdir(temp_files_folder)
    random.shuffle(files)

    for filename in files:
        filepath = os.path.join(temp_files_folder, filename)
        logging.info(f'Обработка файла {filename}')

        try:
            clear_filename, file_extension = os.path.splitext(filename)

            if file_extension.lower() != ".pdf":
                logger.info(f"Файл не был обработан так как это не pdf документ ({filename})")
                os.remove(filepath)
                continue

            # Парсинг и сохранение в XML
            xml_path = parse_and_save_pdf(filepath, temp_files_folder)

            if xml_path is not None:
                upload_file_to_drive(drive, xml_path, drive_folder_id)
                os.remove(xml_path)
                os.remove(filepath)
                logging.info(f"Файл {filename} успешно обработан и загружен на Google диск")
            else:
                logger.info(f"Не удалось определить тип инвойса {filename}")

        except Exception as exc:
            logger.error(f"Ошибка при обработке файла {filename}: {exc}")

