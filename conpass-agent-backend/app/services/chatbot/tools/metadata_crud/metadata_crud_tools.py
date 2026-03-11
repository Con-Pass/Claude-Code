from llama_index.core.tools import FunctionTool

from app.services.chatbot.tools.metadata_crud.read_directory import read_directory
from app.services.chatbot.tools.metadata_crud.read_metadata import read_metadata
from app.services.chatbot.tools.metadata_crud.generate_metadata_key_creation_action import (
    generate_metadata_key_creation_action,
)
from app.services.chatbot.tools.metadata_crud.generate_metadata_key_deletion_action import (
    generate_metadata_key_deletion_action,
)

from app.services.chatbot.tools.metadata_crud.generate_metadata_key_update_action import (
    generate_metadata_key_update_action,
)
from app.services.chatbot.tools.metadata_crud.generate_contract_metadata_update_action import (
    generate_contract_metadata_update_action,
)
from app.services.chatbot.tools.metadata_crud.generate_directory_metadata_visibility_update_action import (
    generate_directory_metadata_visibility_update_action,
)
from app.services.conpass_api_service import ConpassApiService


def get_metadata_crud_tools(
    conpass_api_service: ConpassApiService,
) -> list[FunctionTool]:
    tools = []
    tools.append(
        FunctionTool.from_defaults(
            async_fn=read_metadata,
            name="read_metadata",
            description=(
                "Read and discover metadata information. This is your PRIMARY tool for gathering information. "
                "ALWAYS use this FIRST before any update/create operation to get metadata_id and key_id values. "
                "\n\n"
                "THREE USAGE SCENARIOS:\n"
                "1) Get contract metadata: Provide contract_ids (list of contract IDs) to get metadata names, values, metadata IDs, and key IDs for specific contracts. "
                "Returns metadata_id (for existing metadata with values) and key_id (for all metadata fields, including empty ones). "
                "Use metadata_id to update existing values, and key_id to create values for empty metadata fields. "
                "\n"
                "2) Get metadata keys for a directory: Provide directory_id to get all metadata keys (DEFAULT and FREE) available for a specific directory. "
                "This shows which metadata fields are visible and configured for contracts in that directory. "
                "\n"
                "3) Get all metadata keys in the system: Provide neither contract_ids nor directory_id to get all metadata keys (DEFAULT and FREE) available in the account. "
                "This shows all possible metadata fields that can be used, including their visibility settings and types. "
                "\n\n"
                "CRITICAL INFORMATION RETURNED:\n"
                "- metadata_id: Required for UPDATE operations (only present when field has a value)\n"
                "- key_id: Required for CREATE operations (always present, even for empty fields)\n"
                "- status: Must be ENABLE (status=1) to be updated\n"
                "- lock: Whether metadata is locked (locked metadata can still be updated, tool handles unlocking) "
                "\n\n"
                "WHEN TO USE:\n"
                "- ALWAYS use this FIRST before any update/create operation\n"
                "- User wants to see current metadata for specific contracts\n"
                "- User wants to see which metadata fields are available for a directory\n"
                "- User wants to see all metadata keys in the system\n"
                "- You need to discover metadata_id or key_id values for update/create operations"
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )

    tools.append(
        FunctionTool.from_defaults(
            async_fn=read_directory,
            name="read_directory",
            description=(
                "Read directory information including directory names and directory ids. "
                "Use this to understand which directories are accessed by the user"
                "\n\n"
                "RETURNS:\n"
                "List of Dict containing:\n"
                "- directory_id: Unique identifier for the directory\n"
                "- directory_name: Name of the directory\n"
                "\n\n"
                "WHEN TO USE:\n"
                "- When you want to know which directories are accessible.\n"
                "- To fetch directory id(s) and name(s)"
                "- To update directory metadata operation such as visibility enable or disable etc."
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    tools.append(
        FunctionTool.from_defaults(
            async_fn=generate_contract_metadata_update_action,
            name="generate_contract_metadata_update_action",
            description=(
                "Update or create VALUES for metadata items in a contract (batch operation). "
                "This tool modifies metadata VALUES only - to create new metadata FIELD definitions, use create_metadata_key instead. "
                "\n\n"
                "OPERATIONS SUPPORTED:\n"
                "1) UPDATE existing metadata: Use metadata_id (from read_metadata response) when the metadata already has a value (id is not null). "
                "2) CREATE new metadata value: Use key_id (from read_metadata response) when the metadata field is empty (id is null). "
                "\n\n"
                "REQUIRED PARAMETERS:\n"
                "- contract_id (int): The contract ID to update\n"
                "- updates (list): List of MetadataUpdateItem objects, each containing:\n"
                "  * EITHER metadata_id (for UPDATE) OR key_id (for CREATE) - get these from read_metadata\n"
                "  * At least one of: value, date_value, or lock\n"
                "\n\n"
                "FIELD TYPE REQUIREMENTS (CRITICAL):\n"
                "- DATE fields (contractdate, contractstartdate, contractenddate, cancelnotice, related_contract_date): "
                "  MUST use 'date_value' in YYYY-MM-DD format (e.g., '2024-12-31'). DO NOT use 'value' for date fields.\n"
                "- TEXT fields (title, company names, docid, etc.): "
                "  MUST use 'value' (max 255 characters). DO NOT use 'date_value' for text fields.\n"
                "- CONTRACT_TYPE field (key_id=16, label='conpass_contract_type'): "
                "  MUST use 'value' with one of these exact Japanese values: "
                "'秘密保持契約書', '雇用契約書', '申込注文書', '業務委託契約書', '売買契約書', '請負契約書', "
                "'賃貸借契約書', '派遣契約書', '金銭消費貸借契約', '代理店契約書', '業務提携契約書', "
                "'ライセンス契約書', '顧問契約書', '譲渡契約書', '和解契約書', '誓約書', 'その他'.\n"
                "- PERSON field (key_id=17, label='conpass_person'): "
                "  MUST use 'value' with comma-separated person IDs (e.g., '1,2,3') OR person names (e.g., 'John Doe, Jane Smith'). "
                "The tool automatically resolves names to IDs using fuzzy matching. "
                "If name resolution fails, use numeric IDs instead.\n"
                "\n\n"
                "VALIDATION RULES:\n"
                "- Metadata must be in ENABLE status (status=1) to be updated. Check read_metadata response for status.\n"
                "- If metadata is locked (lock=true) and you're updating value/date_value, the tool automatically unlocks it first, then updates.\n"
                "- Value length cannot exceed 255 characters for text fields.\n"
                "- Date format must be exactly YYYY-MM-DD (e.g., '2024-01-15', not '2024/01/15' or '01-15-2024').\n"
                "- Contract type values must match exactly (case-sensitive, in Japanese).\n"
                "- Person IDs must exist in the system (validated against user list).\n"
                "\n\n"
                "RETURN VALUE:\n"
                "Returns an UpdateMetadataAction object that requires user confirmation before execution. "
                "The action includes all metadata items to be updated/created, with current and new values for comparison. "
                "If validation fails, error_message will contain details about what went wrong.\n"
                "\n\n"
                "USAGE EXAMPLES:\n"
                "- Update contract title: {'metadata_id': 123, 'value': 'New Contract Title'}\n"
                "- Create contract date: {'key_id': 6, 'date_value': '2024-12-31'}\n"
                "- Update person field: {'metadata_id': 456, 'value': '1,2,3'} or {'metadata_id': 456, 'value': 'John Doe, Jane Smith'}\n"
                "- Update contract type: {'metadata_id': 789, 'value': '業務委託契約書'}\n"
                "- Unlock metadata: {'metadata_id': 123, 'lock': False}\n"
                "- Batch update: Multiple items in the updates list\n"
                "\n\n"
                "IMPORTANT NOTES:\n"
                "- Always call read_metadata first to get current metadata state and obtain metadata_id/key_id values.\n"
                "- Use metadata_id when the field already has a value (for UPDATE).\n"
                "- Use key_id when the field is empty (for CREATE).\n"
                "- Date fields and text fields use different parameters (date_value vs value) - this is enforced by validation.\n"
                "- The tool handles locked metadata automatically, but you can also explicitly set lock status.\n"
                "- All updates are batched and require user confirmation before execution."
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    tools.append(
        FunctionTool.from_defaults(
            async_fn=generate_metadata_key_creation_action,
            name="generate_metadata_key_creation_action",
            description=(
                "Create new FREE/custom metadata keys definition at the account level (BATCH OPERATION). "
                "This creates the metadata key DEFINITION (not a value). "
                "IMPORTANT: This is a BATCH operation - you can create MULTIPLE keys in a SINGLE call. "
                "\n\n"
                "IMPORTANT:\n"
                "- This creates the metadata key definition, not a value\n"
                "- The key is created with account-level visibility enabled\n"
                "- To enable this key for a directory, use update_directory_metadata_visibility separately\n"
                "- For updating existing metadata VALUES, use update_contract_metadata instead\n"
                "- BATCH OPERATION: Pass ALL keys you want to create in a SINGLE call, do NOT call this tool multiple times "
                "\n\n"
                "WHEN TO USE:\n"
                "- User wants to add one or more new custom metadata fields to contracts\n"
                "- User wants to create new metadata field definitions (not just values) "
                "\n\n"
                "REQUIRED PARAMETERS:\n"
                "- key_names (list): List of CreateMetadataKey objects with 'name' field. "
                "  Example: [{'name': 'field1'}, {'name': 'field2'}, {'name': 'field3'}]\n"
                "  CRITICAL: Pass ALL keys in a SINGLE call. Do NOT call this tool multiple times for multiple keys."
                "\n\n"
                "RETURN VALUE:\n"
                "Returns a CreateMetadataKeyAction object."
                "The action includes the new metadata key definition details. "
                "\n\n"
                "WORKFLOW:\n"
                "1. Call generate_metadata_key_creation_action ONCE with ALL field names in the key_names parameter\n"
                "2. Stop and return the action template to the user for manual approval\n"
                "3. If user wants to enable it for a directory, use generate_directory_metadata_visibility_update_action separately"
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    tools.append(
        FunctionTool.from_defaults(
            async_fn=generate_metadata_key_deletion_action,
            name="generate_metadata_key_deletion_action",
            description=(
                "Delete a custom metadata key definition from the account level. "
                "This removes the metadata key DEFINITION (not individual values). "
                "\n\n"
                "IMPORTANT:\n"
                "- This deletes the metadata key definition, not individual metadata values in agreements\n"
                "- Only FREE/custom metadata keys can be deleted (not DEFAULT system keys)\n"
                "- Deleting a key affects all agreements that use this metadata field\n"
                "- The key is soft-deleted (status set to DISABLE)\n"
                "- Must first call read_metadata() to get the key_id of the key to delete "
                "\n\n"
                "WHEN TO USE:\n"
                "- User wants to remove a custom metadata field from the system\n"
                "- User wants to delete a metadata field definition they no longer need "
                "\n\n"
                "REQUIRED PARAMETERS:\n"
                "- key_id (int): ID of the metadata key to delete (get from read_metadata first)\n"
                "- name (str): Name of the metadata key to delete (for confirmation) "
                "\n\n"
                "RETURN VALUE:\n"
                "Returns a DeleteMetadataKeyAction object"
                "The action includes the metadata key details to be deleted. "
                "\n\n"
                "WORKFLOW:\n"
                "1. Call read_metadata() to find the key_id for the target key name. Stay silent for this part only.\n"
                "2. Call delete_metadata_key with the key_id and name\n"
                "3. Present the action template to the user for approval"
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    tools.append(
        FunctionTool.from_defaults(
            async_fn=generate_metadata_key_update_action,
            name="generate_metadata_key_update_action",
            description=(
                "Update (rename) an existing FREE/custom metadata key definition at the account level. "
                "This updates the metadata key DEFINITION name (not metadata values). "
                "\n\n"
                "IMPORTANT:\n"
                "- This updates the metadata key definition name, not metadata values\n"
                "- Validates that the current key exists before updating\n"
                "- Prevents duplicate names by checking that no other key has the new name\n"
                "- The key maintains its account-level and directory-level visibility settings\n"
                "- For updating metadata VALUES, use update_contract_metadata instead\n"
                "- For changing directory visibility, use update_directory_metadata_visibility "
                "\n\n"
                "WHEN TO USE:\n"
                "- User wants to rename an existing custom metadata field\n"
                "- User wants to change the display name of a metadata key definition "
                "\n\n"
                "REQUIRED PARAMETERS:\n"
                "- current_name (str): Current display name of the metadata key to update (max 255 characters)\n"
                "- new_name (str): New display name for the metadata key (max 255 characters) "
                "\n\n"
                "VALIDATION:\n"
                "- Both current_name and new_name must be valid strings (non-empty, max 255 characters)\n"
                "- A metadata key with current_name must exist in the system\n"
                "- No other metadata key can already have the new_name (prevents duplicates)\n"
                "- If current_name equals new_name, the update is allowed (no-op) "
                "\n\n"
                "RETURN VALUE:\n"
                "Returns an UpdateMetadataKeyAction object that requires user confirmation before execution. This is *Important*"
                "The action includes the current and new metadata key name for comparison. "
                "If validation fails (key not found, duplicate new name), error_message will contain details. "
                "\n\n"
                "WORKFLOW:\n"
                "1. Call read_metadata() to find the key_id for the target key name. Stay silent for this part only."
                "2. Call update_metadata_key with current_name and new_name\n"
                "3. The function validates that current_name exists and new_name is available\n"
                "4. Ask the user for approval\n"
                "5. After approval, present the action template"
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    tools.append(
        FunctionTool.from_defaults(
            async_fn=generate_directory_metadata_visibility_update_action,
            name="generate_directory_metadata_visibility_update_action",
            description=(
                "Update visibility of metadata keys for a specific directory (batch operation). "
                "This changes which metadata fields are VISIBLE for contracts in a directory (not their values). "
                "\n\n"
                "IMPORTANT:\n"
                "- This changes which metadata fields are visible, not their values\n"
                "- Supports updating multiple metadata keys in a single call\n"
                "- Preserves existing metadata keys that are not being updated "
                "\n\n"
                "WHEN TO USE:\n"
                "- User wants to show or hide specific metadata fields in a directory\n"
                "- User wants to configure which metadata fields are visible for contracts in a directory\n"
                "- User wants to enable a newly created metadata key for a directory "
                "\n\n"
                "REQUIRED PARAMETERS:\n"
                "- directory_id (int): The directory to update\n"
                "- metadata_key_updates (list): List of updates, each with:\n"
                "  * key_id (int): MetaKey ID\n"
                "  * key_type (str): 'DEFAULT' or 'FREE'\n"
                "  * is_visible (bool): New visibility setting "
                "\n\n"
                "RETURN VALUE:\n"
                "Returns an UpdateDirectoryMetadataVisibilityAction object"
                "The action includes all metadata keys to be updated with their current and new visibility settings. "
                "\n\n"
                "WORKFLOW:\n"
                "1. Call read_metadata with directory_id to see current visibility settings\n"
                "2. Show user current state\n"
                "3. Call update_directory_metadata_visibility with desired changes\n"
                "4. Present the action template to the user for approval"
            ),
            partial_params={
                "conpass_api_service": conpass_api_service,
            },
        )
    )
    return tools
