from datetime import datetime
from typing import List
from llama_index.core.tools import FunctionTool
from app.services.chatbot.tools.csv_generation.generate_csv import generate_csv_logic


def get_csv_generation_tool(directory_ids: List[int]) -> FunctionTool:
    today = datetime.now().strftime("%Y-%m-%d")

    return FunctionTool.from_defaults(
        async_fn=generate_csv_logic,
        name="csv_generation_tool",
        description=f"""
        Today's date is {today}.
        
        Generates a CSV file from data provided by previous tools (e.g., contracts, metadata).
        This tool does NOT fetch data itself; it only formatting/processing data you explicitly provide into a CSV.
        
        Use this tool when:
        - The user asks to "generate a CSV", "download as CSV", "export to Excel/CSV".
        - You have ALREADY fetched the necessary data using `metadata_search`, `semantic_search`, `read_contracts` or `get_file_content_tool`.
        
        Args:
            data: REQUIRED. Can be:
            - Output from previous tools (metadata_search, semantic_search, read_contracts_tool, get_file_content_tool)
            - Output from document_diffing_tool (the entire dictionary with diff_content field) - when user wants comparison results in CSV format
            - Any List[Dict] or Dict containing structured data
            You MUST pass the output from previous tools explicitly into this argument. Do NOT leave this empty.
            instruction: The user's specific instruction on what the CSV should contain (e.g., "columns for ID, Title, and Risk Score", "Compare these contracts", "convert comparison to CSV format with columns for differences"). 
            **IMPORTANT**: The CSV column headers will automatically match the language of this instruction. If the instruction is in Japanese, headers will be in Japanese. If in English, headers will be in English. Default is Japanese.
            
        Returns:
            A dictionary containing:
            - success: boolean
            - csv_content: The raw CSV string (THIS IS FOR FRONTEND USE ONLY - DO NOT DISPLAY IT)
            - filename: Suggested filename
            - message: Status message
            
        CRITICAL - Response Format (MANDATORY):
        ⚠️ IMPORTANT: The csv_content in the tool output is AUTOMATICALLY sent to the frontend. You MUST NOT display it, preview it, or show it in any format (markdown tables, plain text, etc.). The frontend will handle displaying the download button.
        
        When this tool is used, you MUST follow these rules EXACTLY - NO EXCEPTIONS:
        When this tool is used, you MUST follow these rules EXACTLY - NO EXCEPTIONS:
        1. DO NOT include CSV content in your text response. The CSV content is automatically available via tool output.
        2. DO NOT create markdown tables showing CSV data - THIS IS STRICTLY FORBIDDEN.
        3. DO NOT show any preview, summary, or excerpt of the CSV data - NO "以下の内容が含まれています" or similar phrases.
        4. DO NOT create ANY links of ANY kind - no data URI links, no markdown links (e.g., [text](link)), no file links, no download links, NO LINKS WHATSOEVER.
        5. DO NOT mention filenames or create any clickable elements.
        6. DO NOT use markdown link syntax [text](url) - this is STRICTLY FORBIDDEN.
        7. DO NOT use markdown table syntax (| column | column |) - this is STRICTLY FORBIDDEN.
        8. ONLY provide a brief confirmation message in the user's language (e.g., "CSVファイルが正常に生成されました。下のボタンをクリックしてダウンロードできます。" for Japanese, or "The CSV file was successfully generated. You can download it by clicking the button below." for English).
        
        ABSOLUTELY NO CSV DATA, NO TABLES, NO LINKS - The frontend automatically displays a download button. Your response must be ONLY the confirmation message, with NO CSV content, NO markdown tables, NO links, NO markdown link syntax, NO additional text, NO previews, and NO formatting that creates clickable elements or displays data.
            
        Example Flow:
        1. User: "Find contracts with Company A and make a CSV"
        2. Agent calls `metadata_search(query="Company A")` -> gets `results`
        3. Agent calls `csv_generation_tool(data=results['contracts'], instruction="List contracts with Company A")`
        4. Tool returns CSV content.
        
        Example Flow 2 (File Content):
        1. User: "Summarize file ID 123 and 456 in a CSV"
        2. Agent calls `get_file_content_tool(file_ids=["123", "456"])` -> gets `content_dict`
        3. Agent calls `csv_generation_tool(data=content_dict, instruction="Colums for File ID and Summary")`

        Example Flow 3 (Mixed Sources - Search + File):
        1. User: "Compare contract 123 with search results for 'NDA' and export CSV"
        2. Agent calls `semantic_search(query="NDA")` -> gets `search_results` (List)
        3. Agent calls `get_file_content_tool(file_ids=["123"])` -> gets `file_content` (Dict)
        4. Agent calls `csv_generation_tool(data={{"search_results": search_results, "specific_file": file_content}}, instruction="Compare key terms")`

        Example Flow 4 (Comparison → CSV Export):
        1. User: "What are the differences between this file and contract 5813? Explain in CSV"
        2. Agent calls `get_file_content_tool(file_ids=[...])` → Returns: file_content = {{"file_id": "content"}}  # DICT format
        3. Agent calls `read_contracts_tool(contract_ids=[5813])` → Returns: contract_data = [{{"contract_id": 5813, "contract_body": "...", "url": "..."}}]  # LIST format
        4. **CRITICAL**: Agent extracts contract_body: contract_body = contract_data[0]["contract_body"]  # Extract string from list
        5. Agent combines: combined_data = {{"file_[file_id]": file_content["file_id"], "contract_5813": contract_body}}  # Combine into single dict
        6. Agent calls `document_diffing_tool(data=combined_data, instruction="compare key differences")` → gets `diff_result` (Dict with diff_content)
        7. Agent calls `csv_generation_tool(data=diff_result, instruction="convert comparison to CSV format with columns for differences")`
        8. Tool returns CSV content.
        """,
    )
