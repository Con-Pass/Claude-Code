# Document Diffing Tool Technical Context

## Overview
We will implement a new tool `document_diffing_tool` for the chat agent. This tool serves as a "comparison engine" to provide differences between provided files in a normal text format. It takes file contents (fetched by `get_file_content_tool`) or other text data and generates a detailed text-based comparison or diff based on user instructions.

## Architecture
We will create a new directory `app/services/chatbot/tools/document_diffing/`.

### Directory Structure
```
app/services/chatbot/tools/document_diffing/
├── __init__.py
├── document_diffing_tool.py      # Main entry point, defines the FunctionTool
├── diff_logic.py                 # Core logic: LLM processing, diff generation
└── prompts.py                    # Prompt templates for the LLM
```

## Implementation Details

### 1. `document_diffing_tool.py`
This file will define `get_document_diffing_tool()`.
It will configure the `FunctionTool` with:
- **Name**: `document_diffing_tool`
- **Description**: Instructions to the Agent.
    - "Use this tool to generate a text-based comparison or difference report between multiple files or text sources."
    - "Do NOT use this tool to fetch file content. Use `get_file_content_tool` first to retrieve the text."
    - **Sources:** `get_file_content_tool`.
    - **Logic:**
        1. Agent receives request (e.g., "What are the differences between File A and File B?").
        2. Agent calls `get_file_content_tool` (or other source) to get the text.
        3. Agent passes result (List[Dict] or Dict) + User Instruction to `document_diffing_tool`.
- **Parameters**:
    - `data` (`Union[List[Dict[str, Any]], Dict[str, Any]]`): The input data to compare. This should be the file contents or text data retrieved from a previous tool call.
    - `instruction` (`str`): The user's specific instruction on how to frame the comparison (e.g., "Highlight changes in liability clauses", "Show added/removed sections").

### 2. `diff_logic.py`
This file will contain the async function `generate_diff_logic`.
**Workflow**:
1.  **Validation**: Ensure `data` is not empty.
2.  **LLM Processing**:
    - Construct a prompt using `prompts.py`.
    - Input: The `data` (context) and the `instruction`.
    - Task: Ask the LLM to analyze the provided texts and output a structured text comparison based on the instruction.
    - The output should be formatted as "normal (usual) text format" as requested, handling things like side-by-side comparison summary, bullet points of changes, or paragraph explanations.
3.  **Response Construction**:
    - Return a dictionary:
    ```python
    {
        "success": True,
        "diff_content": "The main differences are:\n1. Clause A...\n2. Clause B...",
        "message": "Document comparison generated successfully."
    }
    ```

### 3. `prompts.py`
- **System Prompt**: "You are an expert document analyst. Compare the provided text documents and generate a detailed difference report based on the user's instructions. detailed and structured text format."

## Integration
- Update `app/services/chatbot/tools/tools.py` to import `get_document_diffing_tool`.
- Add `get_document_diffing_tool` to the `common_tools` list in `get_all_tools`.

## Usage Examples

**Scenario 1: File Comparison**
User: "Compare the file 'Contract V1' and 'Contract V2' and tell me what changed."
1.  Agent calls `get_file_content_tool(file_ids=["id_v1", "id_v2"])` -> Returns content dict or list.
2.  Agent calls `document_diffing_tool(data=content, instruction="tell me what changed")`.
3.  Tool returns `{ "diff_content": "..." }`.

**Scenario 2: Specific Section Diff**
User: "What are the differences in the Indemnity section between these two files?"
1.  Agent calls `get_file_content_tool(...)`.
2.  Agent calls `document_diffing_tool(data=content, instruction="Compare the Indemnity section")`.
3.  Tool returns `{ "diff_content": "..." }`.

## Dependencies
- `llama_index.llms.openai` or existing LLM service: For LLM interaction.

## Verification Plan
1.  **Manual Test**:
    - Upload two slightly different text files.
    - Ask the agent to compare them.
    - Verify the agent calls `get_file_content_tool` then `document_diffing_tool`.
    - Verify the output is a coherent text comparison.
