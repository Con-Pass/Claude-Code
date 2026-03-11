from typing import Any, Dict, List, Union
from llama_index.core.tools import FunctionTool
from app.core.logging_config import get_logger
from app.services.chatbot.tools.document_diffing.diff_logic import generate_diff_logic

logger = get_logger(__name__)


async def document_diffing(
    data: Union[List[Dict[str, Any]], Dict[str, Any]],
    instruction: str = "Compare the provided documents and highlight key differences, changes, and important distinctions between them.",
) -> Dict[str, Any]:
    """
    Generates a text-based comparison or diff between provided file contents or texts.

    Args:
        data: The content to compare (from get_file_content_tool or other sources).
        instruction: Optional specific instruction for the comparison. If not provided, a default general comparison will be performed.
    """
    return await generate_diff_logic(data, instruction)


def get_document_diffing_tool() -> FunctionTool:
    """
    Creates a FunctionTool for document diffing.
    """
    return FunctionTool.from_defaults(
        async_fn=document_diffing,
        name="document_diffing_tool",
        description="""
        Use this tool to generate a text-based comparison or difference report between multiple files or text sources.
        
        ***IMPORTANT***: This tool does NOT fetch file content itself. You MUST first use `get_file_content_tool` and/or `read_contracts_tool` to retrieve the text content you want to compare, then combine them into a single data structure before passing to this tool.
        
        Use this tool when:
        - User asks for differences or comparison between files (e.g., "compare file A and file B", "what changed in the new contract?", "diff these documents").
        - User asks to compare a file with a contract (e.g., "compare this file with contract 5814", "differences between the uploaded file and contract 1234").
        - User wants a text summary of changes.
        
        **CRITICAL - Combining Multiple Sources (MANDATORY STEPS):**
        ⚠️ **FORMAT MISMATCH WARNING**: `get_file_content_tool` returns a DICT, but `read_contracts_tool` returns a LIST. You MUST handle this difference!
        
        When comparing a file with a contract, you MUST follow these steps EXACTLY:
        1. Call `get_file_content_tool(file_ids=[...])` → Returns: file_content = {"file_id": "content"}  # This is a DICTIONARY
        2. Call `read_contracts_tool(contract_ids=[...])` → Returns: contract_data = [{"contract_id": 1234, "contract_body": "...", "url": "..."}]  # This is a LIST of dictionaries!
        3. **MANDATORY - EXTRACT the contract_body from the list**: contract_body = contract_data[0]["contract_body"]  # CRITICAL: read_contracts_tool returns a LIST, NOT a dict! You MUST access the first element [0], then get "contract_body". Do NOT pass contract_data directly. Do NOT pass the entire list.
        4. **MANDATORY - Combine both into a single dictionary**: combined_data = {"file_[file_id]": file_content["file_id"], "contract_[contract_id]": contract_body}  # Both values must be strings (the actual text content)
        5. **MANDATORY - Pass the combined dictionary**: document_diffing_tool(data=combined_data, instruction="...")  # combined_data must have BOTH keys: one for file, one for contract
        
        **Example: Compare file "abc123" with contract 5814:**
        - Step 1: file_content = get_file_content_tool(file_ids=["abc123"]) → Returns: file_content = {{"abc123": "file text..."}}  # DICT format
        - Step 2: contract_data = read_contracts_tool(contract_ids=[5814]) → Returns: contract_data = [{{"contract_id": 5814, "contract_body": "contract text...", "url": "..."}}]  # LIST format (note the square brackets!)
        - **Step 3 (MANDATORY)**: Extract contract body: contract_body = contract_data[0]["contract_body"]  # CRITICAL: contract_data is a LIST, so use [0] to get first element, then ["contract_body"] to get the text. Result: contract_body = "contract text..."
        - **Step 4 (MANDATORY)**: Combine both: combined_data = {{"file_abc123": file_content["abc123"], "contract_5814": contract_body}}  # Both values are now strings. Result: {{"file_abc123": "file text...", "contract_5814": "contract text..."}}
        - **Step 5 (MANDATORY)**: document_diffing_tool(data=combined_data, instruction="compare key differences")  # Pass combined_data which has 2 keys (file + contract)
        
        ⚠️ **CRITICAL MISTAKES TO AVOID:**
        - ❌ Do NOT pass only file_content to document_diffing_tool (this will result in only 1 document, causing comparison to fail)
        - ❌ Do NOT pass contract_data (the entire list) to document_diffing_tool - it expects a dict, not a list!
        - ❌ Do NOT pass contract_data[0] (the dict with contract_id, contract_body, url) - extract just the contract_body string!
        - ❌ Do NOT skip Step 3 (extracting contract_body from the list) - this is the most common mistake!
        - ❌ Do NOT skip Step 4 (combining both into a single dictionary) - you need BOTH sources in one dict
        - ✓ You MUST extract contract_body from contract_data[0]["contract_body"] (get the string value, not the dict)
        - ✓ You MUST combine both into a single dictionary with both keys (file key + contract key)
        - ✓ You MUST pass the combined dictionary to document_diffing_tool (with 2 keys, not 1)
        
        Args:
            data: REQUIRED. The content to compare. Can be:
            - Output from `get_file_content_tool` (Dict[str, str] mapping file_id to content)
            - Combined dictionary with both file and contract content (see example above)
            - Any dictionary containing the text data to compare
            - **When comparing file + contract**: MUST include BOTH sources. Example: {"file_abc123": "...", "contract_5814": "..."} where contract_5814 value comes from contract_data[0]["contract_body"]
            instruction: OPTIONAL. Specific instruction for the comparison (e.g., "summarize key differences", "show changes in the Indemnity clause", "list added and removed sections"). If not provided, a general comparison will be performed. Providing a specific instruction improves the quality and focus of the comparison.
            
        Returns:
            Dictionary containing:
            - success: Boolean indicating success
            - diff_content: The generated text comparison/diff
            - message: Status message
        
        **CRITICAL - CSV Output Workflow (MANDATORY):**
        - This tool generates TEXT-BASED comparison reports only
        - It does NOT generate CSV files
        - **When user asks for comparison results "in CSV", "as CSV", "CSVでの違い", "CSV形式で", or any variation requesting CSV format:**
          * **STEP 1**: Call this tool (document_diffing_tool) to get the comparison text → returns {"success": True, "diff_content": "...", "message": "..."}
          * **STEP 2**: IMMEDIATELY call csv_generation_tool with the ENTIRE output from step 1: csv_generation_tool(data=document_diffing_result, instruction="convert comparison to CSV format with columns for differences")
          * **YOU MUST CALL BOTH TOOLS** - Do NOT stop after calling document_diffing_tool. The user wants CSV output, so you MUST also call csv_generation_tool.
          * Example workflow: document_diffing_tool → csv_generation_tool (BOTH are required for CSV requests)
        """,
    )
