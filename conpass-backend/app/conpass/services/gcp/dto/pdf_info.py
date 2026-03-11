import dataclasses


@dataclasses.dataclass
class PdfInfo:
    bucket_name: str
    blob_name: str
    blob_size: int
    page_size: int
    contents: bytes

    @property
    def gsutil_uri(self):
        return f"gs://{self.bucket_name}/{self.blob_name}"
