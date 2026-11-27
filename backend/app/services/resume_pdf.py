from dataclasses import dataclass

import pymupdf


class PDFValidationError(ValueError):
    """The uploaded content is not a readable, text-bearing PDF."""


class OCRUnsupportedError(ValueError):
    """The PDF appears to contain scanned pages; OCR is not implemented."""


@dataclass(frozen=True)
class PDFText:
    text: str
    page_count: int


def extract_pdf_text(content: bytes, *, max_pages: int, max_characters: int) -> PDFText:
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except (pymupdf.FileDataError, pymupdf.EmptyFileError, RuntimeError) as exc:
        raise PDFValidationError("The uploaded file is not a valid PDF.") from exc

    with document:
        if document.is_encrypted:
            raise PDFValidationError("Password-protected PDFs are not supported.")
        if document.page_count == 0:
            raise PDFValidationError("The PDF contains no pages.")
        if document.page_count > max_pages:
            raise PDFValidationError(
                f"The PDF exceeds the {max_pages}-page processing limit."
            )

        pages: list[str] = []
        has_images = False
        for page in document:
            pages.append(page.get_text("text"))
            has_images = has_images or bool(page.get_images(full=True))

    text = "\n".join(pages).strip()
    if not text:
        if has_images:
            raise OCRUnsupportedError(
                "This PDF appears to be scanned or image-only. OCR is not supported."
            )
        raise PDFValidationError("The PDF contains no extractable text.")
    if has_images and len(text) < 40:
        raise OCRUnsupportedError(
            "This PDF appears to be scanned or image-only. OCR is not supported."
        )
    if len(text) > max_characters:
        raise PDFValidationError(
            f"The extracted text exceeds the {max_characters}-character processing limit."
        )
    return PDFText(text=text, page_count=len(pages))
