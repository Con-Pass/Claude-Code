# flake8: noqa: E402
from dotenv import load_dotenv
import base64
import json
import logging
import traceback
import asyncio
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from llama_index.core import Document
from doc_generator import get_documents_from_pubsub
from pipeline import generate_datasource
from qdrant_indexes import ensure_payload_indexes
from doc_store import get_redis_doc_store
from vector_db import get_qdrant_vector_store
from model import get_embedding_model
from sparse_model import get_sparse_embedding_model


load_dotenv()

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize shared resources at startup and ensure indexes are created.
    This runs once when the service starts, not on every request.
    """
    logger.info("Initializing shared resources...")

    try:
        # Initialize singleton connections (Redis, Qdrant, embedding models)
        # This ensures connections are ready before first request
        get_redis_doc_store()
        get_qdrant_vector_store()
        get_embedding_model()
        get_sparse_embedding_model()  # Initialize BM25 sparse embedding model

        # Ensure payload indexes are created at startup (once, not per request)
        await ensure_payload_indexes()

        logger.info("Shared resources initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing resources: {e}", exc_info=True)
        # Don't raise - let the service start and handle errors per request

    yield

    # Cleanup (if needed)
    logger.info("Shutting down...")


app = FastAPI(
    title="Generate Embeddings Pipeline",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    """Health check endpoint for Cloud Run"""
    return {"status": "healthy", "service": "generate-embeddings"}


@app.post("/")
async def process_pubsub(request: Request):
    """
    Main endpoint for processing Pub/Sub push messages.
    Cloud Run receives Pub/Sub messages as HTTP POST requests.

    Uses asyncio.to_thread() to run the blocking generate_datasource() function
    in a thread pool, allowing the event loop to handle other requests concurrently.
    """
    try:
        logger.info("Cloud Run triggered - Starting embeddings generation")

        # Get the Pub/Sub message from the request
        envelope = await request.json()

        if not envelope:
            logger.error("No Pub/Sub message received in this batch")

        # source_typeの判定: Pub/Subメッセージのattributesまたはdataから取得
        source_type = "contract"
        message = envelope.get("message", {})
        msg_attributes = message.get("attributes", {})
        if msg_attributes.get("source_type") == "law_regulation":
            source_type = "law_regulation"
        else:
            # data内のsource_typeもチェック
            try:
                encoded = message.get("data", "")
                if encoded:
                    decoded = base64.b64decode(encoded).decode("utf-8")
                    data_dict = json.loads(decoded)
                    if data_dict.get("source_type") == "law_regulation":
                        source_type = "law_regulation"
            except Exception:
                pass

        logger.info(f"Detected source_type: {source_type}")

        # Extract documents from Pub/Sub message
        if source_type == "law_regulation":
            # 法令データはPub/Subメッセージから直接Documentを生成
            documents = _get_law_documents_from_pubsub(envelope)
        else:
            documents = get_documents_from_pubsub(envelope)

        if not documents:
            logger.error("No documents found in this batch")
        else:
            if source_type == "law_regulation":
                law_names = [
                    doc.metadata.get("law_name", "unknown") for doc in documents
                ]
                logger.info(f"Processing {len(documents)} law articles from: {set(law_names)}")
            else:
                # Log contract IDs being processed for better debugging
                contract_ids = [
                    doc.metadata.get("contract_id", "unknown") for doc in documents
                ]
                logger.info(f"Processing {len(documents)} contracts: {contract_ids}")

        # Run blocking generate_datasource() in a thread pool to avoid blocking the event loop
        # This allows FastAPI to handle multiple concurrent requests
        result = await asyncio.to_thread(generate_datasource, documents, source_type)
        nodes = result.get("nodes", []) if isinstance(result, dict) else result
        if source_type == "law_regulation":
            logger.info(
                f"Finished generating {len(nodes)} nodes for law regulations"
            )
        else:
            logger.info(
                f"Finished generating {len(nodes)} nodes for contracts: {contract_ids if documents else []}"
            )

        response_content = {
            "status": "success",
            "message": f"{len(nodes)} nodes generated successfully",
        }

        # エラーハンドリング結果を含める
        if isinstance(result, dict):
            response_content["processed"] = result.get("processed", 0)
            response_content["updated"] = result.get("updated", 0)
            response_content["skipped"] = result.get("skipped", 0)
            response_content["failed"] = result.get("failed", 0)
            response_content["failure_rate"] = result.get("failure_rate", 0.0)
            if result.get("failures"):
                response_content["failures"] = result["failures"]

        return JSONResponse(
            status_code=200,
            content=response_content,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_message = str(e)
        error_traceback = traceback.format_exc()

        logger.error(f"Error in Cloud Run: {error_message}")
        logger.error(f"Traceback: {error_traceback}")

        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": error_message,
                "traceback": error_traceback,
            },
        )


def _get_law_documents_from_pubsub(envelope: dict) -> List[Document]:
    """
    法令規制Pub/SubメッセージからDocumentリストを生成する。

    egov_law_fetcherが発行するメッセージ形式:
    {
        "source_type": "law_regulation",
        "law_name": "民法",
        "articles": [
            {"law_name": "民法", "law_id": "...", "article_number": "第1条",
             "article_title": "...", "text": "..."},
            ...
        ]
    }
    """
    try:
        message = envelope.get("message", {})
        encoded_data = message.get("data", "")
        if not encoded_data:
            logger.error("No data in law regulation Pub/Sub message")
            return []

        batch_json = base64.b64decode(encoded_data).decode("utf-8")
        batch = json.loads(batch_json)

        articles = batch.get("articles", [])
        if not articles:
            logger.warning("No articles in law regulation message")
            return []

        docs = []
        for article in articles:
            text = article.get("text", "").strip()
            if not text:
                continue

            metadata = {
                "law_name": article.get("law_name", ""),
                "law_id": article.get("law_id", ""),
                "article_number": article.get("article_number", ""),
                "article_title": article.get("article_title", ""),
                "source_type": "law_regulation",
            }

            doc_id = f"{article.get('law_id', '')}_{article.get('article_number', '')}"
            docs.append(
                Document(
                    id_=doc_id,
                    text=text,
                    metadata=metadata,
                )
            )

        logger.info(
            f"Extracted {len(docs)} law article documents from Pub/Sub message"
        )
        return docs

    except Exception as e:
        logger.error(f"Error extracting law documents from Pub/Sub: {e}", exc_info=True)
        return []


if __name__ == "__main__":
    import uvicorn

    # For local testing
    uvicorn.run(app, host="0.0.0.0", port=8080)
