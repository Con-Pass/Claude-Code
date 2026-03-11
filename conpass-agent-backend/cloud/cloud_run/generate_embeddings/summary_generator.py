import logging
from llama_index.llms.openai import OpenAI
from embedding_pipeline_config import embedding_pipeline_config


logger = logging.getLogger(__name__)

SUMMARY_MAX_WORDS = 200


def generate_summary(contract_text: str) -> str | None:
    try:
        llm = OpenAI(
            model=embedding_pipeline_config.SUMMARY_MODEL,
            api_key=embedding_pipeline_config.OPENAI_API_KEY,
            temperature=0.5,
        )

        prompt = f"""
            You are a helpful assistant that generates a summary of a contract. Your task is to extract the most important information from the contract and make a short 1 paragraph summary of the contract. The summary should be no more than {SUMMARY_MAX_WORDS - (SUMMARY_MAX_WORDS * 0.25)} words and it should be in Japanese.
            Here is the contract text:
            {contract_text}
        """

        res = llm.complete(prompt)

        summary = res.text

        logger.info(f"Summary: {summary}")

        if get_summary_length(summary) > SUMMARY_MAX_WORDS:
            summary = truncate_summary(summary, SUMMARY_MAX_WORDS)

        return summary
    except Exception as e:
        logger.exception(f"Error generating summary: {e}")
        return None


def get_summary_length(summary: str) -> int:
    return len(summary.split())


def truncate_summary(summary: str, max_words: int) -> str:
    words = summary.split()
    return " ".join(words[:max_words])
