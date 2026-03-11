import collections
from typing import List

from google.cloud import vision
import json
from logging import getLogger

from conpass.services.gcp.cloud_storage import GoogleCloudStorage, GCSBucketName

logger = getLogger(__name__)


class GoogleCloudVision:
    output_bucket_name = GCSBucketName.API.value

    def scan_image(self, filename: str):
        """
        filename: GCS上のbucket内のファイル名
        画像としてスキャンする（画像ファイルにしかつかえません）
        結果を[text]で返す
        """
        vision_client = vision.ImageAnnotatorClient()
        cloudstorage = GoogleCloudStorage()
        client, bucket = cloudstorage.get_cloudstorage()
        filepath = 'gs://' + bucket.name + '/' + filename
        filesource = vision.ImageSource(gcs_image_uri=filepath)
        image = vision.Image(source=filesource)
        output_texts = []
        try:
            response = vision_client.document_text_detection(
                image=image,
                image_context={'language_hints': ['ja']}
            )
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            output_texts.append(''.join([
                                symbol.text for symbol in word.symbols
                            ]))
        except Exception as e:
            print(e)

        return output_texts

    def scan_pdf(self, filename: str):
        """
        filename: GCS上のbucket内のファイル名
        pdf/tiffをスキャンする
        結果を[text]で返す
        """
        cloudstorage = GoogleCloudStorage()
        gcs_client, bucket = cloudstorage.get_cloudstorage()
        filepath = 'gs://' + bucket.name + '/' + filename

        mime_type = 'application/pdf'

        # jsonファイルに何ページ分を含めるか
        # pdfが5pでbatch_sizeが2の場合、1-2、3-4,5の３ファイルが作られる
        batch_size = 100

        client = vision.ImageAnnotatorClient()

        feature = vision.Feature(
            type_=vision.Feature.Type.TEXT_DETECTION)

        gcs_source = vision.GcsSource(uri=filepath)

        input_config = vision.InputConfig(
            gcs_source=gcs_source, mime_type=mime_type)

        # 結果保存先は一意にする
        dst_path = f"vision/{filename}/"
        output_bucket = gcs_client.get_bucket(self.output_bucket_name)
        # 同じ階層があったら消しておく
        blob_list = [blob for blob in output_bucket.list_blobs(prefix=dst_path) if not blob.name.endswith('/')]
        for blob in blob_list:
            blob.delete()

        gcs_destination = vision.GcsDestination(uri=f"gs://{self.output_bucket_name}/{dst_path}")
        output_config = vision.OutputConfig(
            gcs_destination=gcs_destination, batch_size=batch_size)

        async_request = vision.AsyncAnnotateFileRequest(
            features=[feature], input_config=input_config,
            output_config=output_config, image_context=vision.ImageContext(language_hints=["ja"]))

        operation = client.async_batch_annotate_files(
            requests=[async_request])

        logger.info('Waiting for the operation to finish.')
        operation.result(timeout=180)

        # List objects with the given prefix, filtering out folders.
        blob_list = [blob for blob in output_bucket.list_blobs(prefix=dst_path) if not blob.name.endswith('/')]
        json_list = []
        logger.info('Output files:')
        for blob in blob_list:
            logger.info(blob.name)
            json_list.append(blob.download_as_string())

        texts = self._parse_jsons(json_list)
        return "".join(texts)

    def _parse_jsons(self, jsontext_list: List[str]):
        result = []
        for jsontext in jsontext_list:
            jsondict = json.loads(jsontext, object_pairs_hook=collections.OrderedDict)
            for response in jsondict["responses"]:
                # PDFのページ内にテキストが無い場合は、fullTextAnnotationのキーは含まれないためKeyErrorとなる
                try:
                    text = response["fullTextAnnotation"]["text"]
                    result.append(text)
                except KeyError:
                    logger.info('fullTextAnnotation key not found due to empty page with no text.')
        return result
