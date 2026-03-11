from logging import getLogger
from typing import List

from google.cloud import vision

from common.utils import iter_utils
from conpass.services.gcp.dto.pdf_info import PdfInfo

logger = getLogger(__name__)


class VisionService:
    def __init__(self):
        self.client = vision.ImageAnnotatorClient()

    def get_pdf_text_for_sync(self, pdf_info: PdfInfo) -> str:
        assert pdf_info.page_size <= 30, "31P以上の場合は非同期処理を利用してください"

        client = vision.ImageAnnotatorClient()
        input_config = {"mime_type": "application/pdf", "content": pdf_info.contents}
        features = [{"type_": vision.Feature.Type.DOCUMENT_TEXT_DETECTION}]

        per_page = 5
        text_list: List[str] = []
        for pages in iter_utils.iterable_split(list(range(1, pdf_info.page_size + 1)), per_page):
            requests = [{"input_config": input_config, "features": features, "pages": pages, "image_context": vision.ImageContext(language_hints=["ja"])}]
            response = client.batch_annotate_files(requests=requests)
            for image_response in response.responses[0].responses:
                text_list.append(image_response.full_text_annotation.text)

        return "".join(text_list)
