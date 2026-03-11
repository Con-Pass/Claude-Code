from app.core.logging_config import get_logger
from app.services.chatbot.tools.utils.document_store import get_document_from_docstore
from llama_index.core.tools import FunctionTool
from datetime import datetime
from typing import List, Optional
from app.core.config import settings
from app.services.conpass_api_service import ConpassApiService

logger = get_logger(__name__)

MAX_CONTRACTS_TO_READ = 4


async def read_contracts(
    directory_ids: List[int], contract_ids: list[int], conpass_api_service: Optional[ConpassApiService] = None
) -> list[dict]:
    try:
        logger.info(
            f"read_contracts_tool called with directory_ids: {directory_ids} and contract_ids: {contract_ids}"
        )
        if len(contract_ids) > MAX_CONTRACTS_TO_READ:
            return [
                {
                    "error_message": f"Error: You can only read up to {MAX_CONTRACTS_TO_READ} contracts at a time.",
                }
            ]
        contracts = []
        for contract_id in contract_ids:
            try:
                logger.info(f"Fetching contract body for contract {contract_id}")
                contract_response = await get_document_from_docstore(
                    directory_ids, contract_id, conpass_api_service
                )

                if not contract_response:
                    logger.warning(f"Contract {contract_id} not found in docstore")
                    contracts.append(
                        {
                            "contract_id": contract_id,
                            "error_message": f"Contract {contract_id} not found in docstore",
                        }
                    )
                    continue

                contract_body = contract_response["full_text"]
                contracts.append(
                    {
                        "contract_id": contract_id,
                        "contract_body": contract_body,
                        "url": f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}",
                    }
                )
            except Exception:
                logger.exception(
                    f"Error reading contract body for contract {contract_id}"
                )
                contracts.append(
                    {
                        "contract_id": contract_id,
                        "error_message": f"Error reading contract {contract_id}",
                    }
                )
        return contracts
    except Exception as e:
        logger.exception(f"Error reading contracts: {e}")
        return [
            {
                "error": "An unexpected error occurred while reading contracts",
            }
        ]


def get_read_contracts_tool(directory_ids: List[int], conpass_api_service: ConpassApiService) -> FunctionTool:
    today = datetime.now().strftime("%Y-%m-%d")
    return FunctionTool.from_defaults(
        async_fn=read_contracts,
        name="read_contracts_tool",
        description=f"""
        Today's date is {today}.

        Fetches the full text of SPECIFIC contracts (by ID) to answer detailed questions or provide complete contract text (max {MAX_CONTRACTS_TO_READ} at once).

        Use this tool when
        - The user specifies a CONTRACT ID (or IDs) and wants information FROM that contract
        - The user asks for extraction, explanation, or summary of a SPECIFIC contract
        - The user clearly asks to read/show/display the full contract text
        - You need full contract text to accurately answer questions about ONE or FEW specific contracts
        - Keywords: "contract [ID]", "in contract X", "from contract X", "what does contract X say"

        Do NOT use this tool when
        - The user wants to discover WHICH contracts have something → use semantic_search instead
        - The user wants to filter by metadata (company, dates) → use metadata_search instead
        - The task is risk assessment → use risk_analysis_tool instead
        - The user has not specified contract IDs yet

        Critical routing examples
        - "What are the SLA terms in contract 4824?" → read_contracts_tool ✓ (specific contract ID)
        - "Extract payment terms from contract 1234" → read_contracts_tool ✓ (specific contract ID)
        - "Summarize contract 9999" → read_contracts_tool ✓ (specific contract ID)
        - "Which contracts have SLA terms?" → semantic_search ✓ (discover across many)
        - "Find contracts with ABC Corp" → metadata_search ✓ (metadata only)

        Args:
            contract_ids: List of contract IDs to read (max {MAX_CONTRACTS_TO_READ} at a time).

        Returns:
            A list of dictionaries with:
            - contract_id: The ID of the contract
            - contract_body: The full text of the contract
            - error_message: Present if a contract cannot be retrieved
            - url: The url link of the contract

        Note: For long contracts, prefer summarizing key sections instead of dumping all text to the user.

        """,
        partial_params={"directory_ids": directory_ids, "conpass_api_service": conpass_api_service},
    )
