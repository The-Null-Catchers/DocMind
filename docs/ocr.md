# OCR

OCR is provider-based. The local provider is Tesseract with `ara+eng` by default, which keeps development free and supports mixed Arabic/English pages.

For PDFs, text extraction is attempted first. Pages with insufficient embedded text are rasterized and OCR'd individually. Image uploads go directly to OCR. `DocumentPage` stores `ocr_used`, confidence where available and page metadata.

A future paid OCR provider can implement the same interface and optionally return bounding boxes/table structure. Manual reprocessing is exposed through the document reprocess endpoint.
