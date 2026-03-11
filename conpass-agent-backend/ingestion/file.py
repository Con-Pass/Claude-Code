from app.core.logging_config import get_logger
from pydantic import BaseModel

from app.core.config import settings

logger = get_logger(__name__)


class FileLoaderConfig(BaseModel):
    use_llama_parse: bool = False


def get_file_documents(config: FileLoaderConfig):
    from llama_index.core.readers import SimpleDirectoryReader

    try:
        reader = SimpleDirectoryReader(
            settings.DATA_DIR,
            recursive=True,
            filename_as_id=True,
            raise_on_error=True,
            file_extractor=None,
        )
        return reader.load_data()
    except Exception as e:
        import sys
        import traceback

        # Catch the error if the data dir is empty
        # and return as empty document list
        _, _, exc_traceback = sys.exc_info()
        function_name = traceback.extract_tb(exc_traceback)[-1].name
        if function_name == "_add_files":
            logger.warning(
                f"Failed to load file documents, error message: {e} . Return as empty document list."
            )
            return []
        else:
            # Raise the error if it is not the case of empty data dir
            raise e
