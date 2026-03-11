import time
from app.services.chatbot.index import get_index
from app.core.logging_config import get_logger
from app.core.model_settings import init_model_settings
from app.services.chatbot.postprocessing.node_postprocessor import URLNodePostprocessor

start_time = time.time()
logger = get_logger(__name__)

# Initialize model settings to ensure embedding dimensions match Qdrant collection
init_model_settings()

index = get_index()
engine = index.as_query_engine(node_postprocessors=[URLNodePostprocessor()])

response = engine.query(
    "Which contracts talk about Japan Purple? Return the contract URL with the answer"
)
end_time = time.time()

elapsed_time = end_time - start_time

print(f"Query executed in {elapsed_time:.2f} seconds ({elapsed_time * 1000:.2f} ms)")
print(response)
for node in response.source_nodes:
    print(node)
