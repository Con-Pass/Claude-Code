from app.core.logging_config import get_logger
from app.core.config import settings
from llama_index.llms.openai import OpenAIResponses
from llama_index.core.tools import FunctionTool
from datetime import datetime

logger = get_logger(__name__)


class WebSearchTool:
    def __init__(self):
        self.openai_api_key = settings.OPENAI_API_KEY
        self.llm_model = "gpt-4o-mini"
        self.llm_temperature = 0.3
        self.tools = [
            {
                "type": "web_search",
                "user_location": {
                    "country": "JP",
                    "timezone": "Asia/Tokyo",
                    "city": "Tokyo",
                    "region": "Tokyo",
                    "type": "approximate",
                },
            }
        ]

    def get_web_search_llm(self) -> OpenAIResponses:
        return OpenAIResponses(
            model=self.llm_model,
            api_key=self.openai_api_key,
            temperature=self.llm_temperature,
            built_in_tools=self.tools,
            verbose=True,
            include=["web_search_call.action.sources"],
        )

    async def web_search_tool(self, query: str) -> dict:
        try:
            logger.info(f"web_search_tool called with query: {query}")
            llm = self.get_web_search_llm()

            response = llm.complete(query)
            logger.info(f"Response: {response.raw}")
            return {
                "feedback": f"Web search performed successfully with query: {query}",
                "results": response.text,
            }
        except Exception:
            logger.exception(f"Error calling web_search_tool with query: {query}")
            return {
                "feedback": f"Error calling web_search_tool with query: {query}",
                "results": "",
            }


def get_web_search_tools() -> FunctionTool:
    tool = WebSearchTool()
    today = datetime.now().strftime("%Y-%m-%d")
    return FunctionTool.from_defaults(
        async_fn=tool.web_search_tool,
        name="web_search_tool",
        description=f"""
        Today's date is {today}.

        External web search for information OUTSIDE the contract database. Use only when internal contract data is insufficient and you need up-to-date external information.

        Use this tool when
        - User asks about laws/regulations/legal precedents or industry standards relevant to contracts
        - User needs current company/market information for contract context or due diligence
        - External, time-sensitive information is required to complete the answer
        - Questions about regulations, compliance requirements, or legal frameworks
        - Keywords: "latest law", "current regulations", "industry standards", "legal precedents"

        Do NOT use this tool when
        - Question can be answered from existing contract data → use metadata_search, semantic_search, or read_contracts_tool instead
        - User asks about specific contracts or contract content → use contract tools instead
        - Request is unrelated to contract management → politely redirect

        Critical routing examples
        - "What are the latest privacy law changes in Japan?" → web_search_tool ✓ (external regulation info)
        - "What are industry standards for SLAs?" → web_search_tool ✓ (external standards)
        - "Which contracts have SLA terms?" → semantic_search ✓ (internal contract content)
        - "What are the SLA terms in contract 4824?" → read_contracts_tool ✓ (specific contract)
        - "Find contracts with ABC Corp" → metadata_search ✓ (contract metadata)

        Call guidance
        - Pass the user's detailed question and context verbatim.
        - The tool returns formatted web search findings; summarize concisely for the user.

        Returns:
            - feedback: Status of the search.
            - results: Formatted search result text.
        """,
    )
