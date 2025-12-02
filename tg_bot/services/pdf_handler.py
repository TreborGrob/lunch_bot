import fitz  # need PyMuPDF


def get_text_from_pdf(path_pdf: str) -> str:

    # Открытие PDF-документа
    pdf_document = fitz.open(path_pdf)
    all_text = ""
    # Извлечение текста со всех страниц
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text = page.get_text()
        all_text += text
    # Закрытие документа
    pdf_document.close()
    return all_text


if __name__ == "__main__":
    print(get_text_from_pdf("C:\\Users\\Grob\\Documents\\МЕНЮ ПОСТНОЕ 2025 Г..pdf"))
