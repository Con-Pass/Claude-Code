# import os
# from llama_index.core.query_engine import NLSQLTableQueryEngine
# from llama_index.core import SQLDatabase
# from llama_index.core.prompts import PromptTemplate
# from llama_index.core.prompts.prompt_type import PromptType
# from sqlalchemy import create_engine
# from llama_index.core.settings import Settings as LLamaIndexSettings
# from dotenv import load_dotenv

# load_dotenv()

# db_host = "34.146.70.105"
# db_pass = os.getenv("DB_PASS")
# db_username = "conpass_ai_agent"
# db_port = 3306
# db_name = "conpass"


# connection_string = (
#     f"mysql+pymysql://{db_username}:{db_pass}@{db_host}:{db_port}/{db_name}"
# )

# engine = create_engine(connection_string)

# # Custom table information to help the LLM understand table structure and relationships
# custom_table_info = {
#     "conpass_contract": (
#         "Main table storing basic contract records. This is the primary table - other tables link to contracts via contract_id. "
#         "IMPORTANT: This table contains only LIMITED/BASIC information about contracts. "
#         "MOST contract information (metadata fields and body content) is stored in conpass_metadata and conpass_contractbody tables. "
#         "To get complete contract information, you MUST join with conpass_metadata and conpass_contractbody tables. "
#         "Key columns: "
#         "- id (BIGINT): unique identifier, primary key "
#         "- name (VARCHAR): contract name "
#         "- type (INTEGER): contract type "
#         "- status (INTEGER): contract status "
#         "- created_at, updated_at (DATETIME): timestamps "
#         "- account_id, client_id, directory_id (BIGINT): foreign keys to related entities "
#         "- template_id, origin_id, parent_id, related_parent_id (BIGINT): self-referential foreign keys for contract relationships "
#         "- version (VARCHAR): contract version "
#         "- is_garbage, is_provider, is_open, is_new_lease, is_child_contract (TINYINT): boolean flags "
#         "- bulk_zip_path (VARCHAR): path to bulk zip file if applicable. "
#         "Key relationships: "
#         "- id links to conpass_contractbody.contract_id (contract content/body - contains MOST contract data) "
#         "- id links to conpass_metadata.contract_id (contract metadata fields - contains MOST contract data). "
#         "Use this table as the base when querying contracts, but always join with metadata and contractbody for complete information."
#     ),
#     "conpass_contractbody": (
#         "Stores the actual content/body text of contracts. "
#         "IMPORTANT: This table contains MOST of the contract data (the actual contract text/body). "
#         "To get complete contract information, you MUST join this table with conpass_contract. "
#         "Key columns: "
#         "- id (BIGINT): unique identifier "
#         "- body (LONGTEXT): the actual contract text content (contains MOST contract data) "
#         "- contract_id (BIGINT): foreign key to conpass_contract.id "
#         "- status (INTEGER): status of the contract body "
#         "- version (VARCHAR): version of the contract body "
#         "- is_adopted (TINYINT): whether this version is adopted "
#         "- created_at, updated_at (DATETIME): timestamps. "
#         "Linked to conpass_contract via contract_id = conpass_contract.id. "
#         "When fetching complete contract information, always JOIN this table to get the contract body content."
#     ),
#     "conpass_metadata": (
#         "Stores flexible metadata fields for contracts. This table uses a key-value pattern. "
#         "IMPORTANT: This table contains MOST of the contract data (all metadata fields like dates, amounts, companies, etc.). "
#         "Each row represents one metadata field for a contract. "
#         "To get complete contract information, you MUST join this table with conpass_contract. "
#         "To understand what each metadata value represents, you MUST also join with conpass_metakey using key_id. "
#         "Key columns: "
#         "- id (BIGINT): unique identifier "
#         "- contract_id (BIGINT): foreign key to conpass_contract.id - use this to look up all metadata for a contract "
#         "- key_id (BIGINT): foreign key to conpass_metakey.id (defines what this metadata represents) "
#         "- value (VARCHAR): stores text/numeric metadata values "
#         "- date_value (DATE): stores date-type metadata (end dates, start dates, etc.) "
#         "- choice_value (VARCHAR): stores choice-type metadata values "
#         "- choice_key (INTEGER): choice key identifier "
#         "- choice_selector (VARCHAR): choice selector value "
#         "- score (DOUBLE): confidence score for extracted metadata "
#         "- start_offset, end_offset (INTEGER): character offsets in the contract text "
#         "- check (TINYINT), checked_by_id (BIGINT): verification fields "
#         "- lock (TINYINT): lock flag "
#         "- status (INTEGER): metadata status "
#         "- created_at, updated_at (DATETIME): timestamps. "
#         "A single contract can have multiple metadata entries (one row per metadata field). "
#         "To filter by specific metadata types (like 'end_date'), you must JOIN with conpass_metakey "
#         "to identify the correct metadata key using conpass_metakey.name or conpass_metakey.label. "
#         "IMPORTANT: Only use conpass_metakey rows where type=1 when joining with this table."
#     ),
#     "conpass_metakey": (
#         "Defines the types/categories of metadata that can be stored. "
#         "This is a reference table that describes what each metadata entry represents. "
#         "Key columns: "
#         "- id (BIGINT): unique identifier, referenced by conpass_metadata.key_id "
#         "- name (VARCHAR): the programmatic name of the metadata key (e.g., 'end_date', 'start_date', 'amount') "
#         "- label (VARCHAR): the human-readable label for the metadata key "
#         "- type (INTEGER): metadata key type - CRITICAL: only use rows where type=1 "
#         "- is_visible (TINYINT): whether this metadata key is visible "
#         "- status (INTEGER): status of the metadata key "
#         "- account_id (BIGINT): foreign key to account "
#         "- created_at, updated_at (DATETIME): timestamps. "
#         "CRITICAL FILTERING REQUIREMENT: "
#         "You MUST always filter this table to only include rows where type=1. "
#         "When JOINing with conpass_metadata, always add: WHERE conpass_metakey.type = 1 "
#         "Example: JOIN conpass_metakey mk ON conpass_metadata.key_id = mk.id WHERE mk.type = 1 AND mk.name = 'end_date'"
#     ),
# }

# sql_db = SQLDatabase(
#     engine,
#     include_tables=[
#         "conpass_contract",
#         "conpass_metadata",
#         "conpass_contractbody",
#         "conpass_metakey",
#     ],
#     custom_table_info=custom_table_info,
# )

# # Custom prompt template that instructs the LLM to use JOINs when explaining contracts
# CUSTOM_TEXT_TO_SQL_TMPL = (
#     "Given an input question, first create a syntactically correct {dialect} "
#     "query to run, then look at the results of the query and return the answer. "
#     "You can order the results by a relevant column to return the most "
#     "interesting examples in the database.\n\n"
#     "Never query for all the columns from a specific table, only ask for a "
#     "few relevant columns given the question.\n\n"
#     "Pay attention to use only the column names that you can see in the schema "
#     "description. "
#     "Be careful to not query for columns that do not exist. "
#     "Pay attention to which column is in which table. "
#     "Also, qualify column names with the table name when needed.\n\n"
#     "=== TABLE RELATIONSHIPS ===\n"
#     "The contract tables are related as follows:\n"
#     "- conpass_contract.id = conpass_contractbody.contract_id (contract body/content)\n"
#     "- conpass_contract.id = conpass_metadata.contract_id (contract metadata)\n"
#     "- conpass_metadata.key_id = conpass_metakey.id (metadata key definitions)\n\n"
#     "IMPORTANT: Understanding Contract Data Distribution:\n"
#     "- conpass_contract table contains only basic/limited information about contracts\n"
#     "- MOST contract information is stored in conpass_metadata and conpass_contractbody tables\n"
#     "- To get complete contract information, you MUST join all three tables\n\n"
#     "conpass_metadata stores various metadata fields for contracts. Each metadata entry has:\n"
#     "- contract_id: links to the contract\n"
#     "- key_id: links to conpass_metakey which defines what this metadata represents (name, label)\n"
#     "- date_value: for date-type metadata (end dates, start dates, etc.)\n"
#     "- value: for text/numeric metadata\n"
#     "- choice_value: for choice-type metadata\n\n"
#     "=== FETCHING COMPLETE CONTRACT INFORMATION ===\n"
#     "When asked to 'explain', 'describe', 'show details', or provide comprehensive information about a contract, "
#     "you MUST follow this complete data retrieval pattern:\n\n"
#     "1. Start with conpass_contract table (contains basic contract info like id, name, type, status)\n"
#     "2. JOIN conpass_metadata ON conpass_contract.id = conpass_metadata.contract_id\n"
#     "   - This gives you all metadata values for the contract\n"
#     "   - A contract can have multiple metadata rows (one per metadata field)\n"
#     "3. JOIN conpass_metakey ON conpass_metadata.key_id = conpass_metakey.id AND conpass_metakey.type = 1\n"
#     "   - This maps each metadata value to its key (name/label) so you know what each value represents\n"
#     "   - CRITICAL: Always filter conpass_metakey with type=1\n"
#     "4. JOIN conpass_contractbody ON conpass_contract.id = conpass_contractbody.contract_id\n"
#     "   - This provides the actual contract body/text content\n\n"
#     "Complete contract query pattern:\n"
#     "SELECT con.*, meta.value, meta.date_value, meta.choice_value, mk.name as metadata_key_name, mk.label as metadata_key_label, cb.body\n"
#     "FROM conpass_contract con\n"
#     "LEFT JOIN conpass_metadata meta ON con.id = meta.contract_id\n"
#     "LEFT JOIN conpass_metakey mk ON meta.key_id = mk.id AND mk.type = 1\n"
#     "LEFT JOIN conpass_contractbody cb ON con.id = cb.contract_id\n"
#     "WHERE con.id = [contract_id]\n\n"
#     "Note: Since a contract can have multiple metadata entries, this will return multiple rows (one per metadata field).\n"
#     "You may need to aggregate or structure the results appropriately.\n\n"
#     "=== JOIN GUIDELINES ===\n"
#     "For filtering queries, you may need to JOIN conpass_metadata and conpass_metakey to filter by metadata fields.\n"
#     "When filtering by metadata, consider joining with conpass_metakey to identify the correct metadata key.\n"
#     "Use DISTINCT or GROUP BY when JOINs might create duplicate rows.\n\n"
#     "=== DATE FILTERING RULES ===\n"
#     "CRITICAL: When filtering by date ranges (e.g., 'in December 2025', 'in 2025', 'during Q1', 'this month'), "
#     "you MUST use date range conditions, NOT exact date matches. "
#     "Examples:\n"
#     "- 'contracts that end in December 2025' → date_value >= '2025-12-01' AND date_value <= '2025-12-31'\n"
#     "- 'contracts that end in 2025' → date_value >= '2025-01-01' AND date_value <= '2025-12-31'\n"
#     "- 'contracts ending in Q1 2025' → date_value >= '2025-01-01' AND date_value <= '2025-03-31'\n"
#     "- 'contracts ending this year' → date_value >= '2025-01-01' AND date_value <= '2025-12-31' (use current year)\n"
#     "- 'contracts ending next month' → calculate next month's date range\n"
#     "Never use exact date equality (=) when the question asks for a month, year, quarter, or relative time period.\n"
#     "Only use exact date equality when the user specifies an exact date.\n\n"
#     "=== METADATA FILTERING ===\n"
#     "When filtering by contract metadata (end dates, start dates, amounts, companies, etc.):\n"
#     "- You may need to JOIN conpass_metadata and conpass_metakey to identify the correct metadata key\n"
#     "- CRITICAL: Always filter conpass_metakey to only include rows where type=1\n"
#     "- Use conpass_metakey.name or conpass_metakey.label to identify what the metadata represents\n"
#     "- Filter on conpass_metadata.date_value for dates, conpass_metadata.value for text/numeric values\n"
#     "- If the schema shows metadata key names, use them to filter appropriately\n"
#     "- Consider that a contract may have multiple metadata entries, so use appropriate JOINs and filters\n"
#     "Example query for filtering by end date:\n"
#     "SELECT con.id, con.name, meta.date_value\n"
#     "FROM conpass_contract con\n"
#     "JOIN conpass_metadata meta ON con.id = meta.contract_id\n"
#     "JOIN conpass_metakey mk ON meta.key_id = mk.id\n"
#     "WHERE mk.type = 1 AND mk.name = 'end_date' AND meta.date_value >= '2025-12-01' AND meta.date_value <= '2025-12-31'\n\n"
#     "=== TEXT SEARCH ===\n"
#     "For text searches in contract names or metadata values:\n"
#     "- Use LIKE with wildcards: column_name LIKE '%search_term%'\n"
#     "- For case-insensitive searches, use LOWER() or UPPER() functions\n"
#     "- Example: LOWER(conpass_contract.name) LIKE '%keyword%'\n\n"
#     "=== AGGREGATION AND COUNTING ===\n"
#     "When asked for counts, totals, averages, or other aggregations:\n"
#     "- Use appropriate aggregate functions: COUNT(), SUM(), AVG(), MAX(), MIN()\n"
#     "- Use GROUP BY when grouping results\n"
#     "- Use HAVING for filtering aggregated results\n\n"
#     "=== NULL HANDLING ===\n"
#     "Be aware that metadata fields may be NULL. Use appropriate NULL handling:\n"
#     "- Use IS NULL or IS NOT NULL for NULL checks\n"
#     "- Consider using COALESCE() for default values\n"
#     "- LEFT JOINs may produce NULLs - filter appropriately\n\n"
#     "=== TABLE ALIASES AND RESERVED WORDS ===\n"
#     "CRITICAL: When using table aliases, NEVER use MySQL reserved words as alias names.\n"
#     "Common reserved words to avoid: key, order, group, select, from, where, join, table, index, etc.\n"
#     "Recommended safe aliases:\n"
#     "- conpass_contract → con or c\n"
#     "- conpass_metadata → meta or m\n"
#     "- conpass_metakey → mk (NOT 'key' - it's a reserved word!)\n"
#     "- conpass_contractbody → cb or body\n"
#     "Example of CORRECT usage:\n"
#     "SELECT con.id, con.name, meta.date_value\n"
#     "FROM conpass_contract con\n"
#     "JOIN conpass_metadata meta ON con.id = meta.contract_id\n"
#     "JOIN conpass_metakey mk ON meta.key_id = mk.id\n"
#     "WHERE mk.type = 1 AND mk.name = 'end_date'\n"
#     "Example of INCORRECT usage (will cause SQL syntax error):\n"
#     "JOIN conpass_metakey key ON ... (WRONG - 'key' is reserved)\n\n"
#     "=== GENERAL QUERY BEST PRACTICES ===\n"
#     "- Use WHERE clauses to filter data before JOINs when possible for better performance\n"
#     "- Use appropriate indexes by filtering on indexed columns (like contract_id, key_id)\n"
#     "- When returning contract lists, include relevant identifying information (id, name)\n"
#     "- Use ORDER BY to sort results meaningfully (e.g., by date DESC for recent items)\n"
#     "- Limit results when appropriate using LIMIT\n"
#     "- Use DISTINCT when JOINs might create duplicate rows\n"
#     "- Always use safe table aliases that are NOT MySQL reserved words\n\n"
#     "You are required to use the following format, each taking one line:\n\n"
#     "Question: Question here\n"
#     "SQLQuery: SQL Query to run\n"
#     "SQLResult: Result of the SQLQuery\n"
#     "Answer: Final answer here\n\n"
#     "Only use tables listed below.\n"
#     "{schema}\n\n"
#     "Question: {query_str}\n"
#     "SQLQuery: "
# )

# CUSTOM_TEXT_TO_SQL_PROMPT = PromptTemplate(
#     CUSTOM_TEXT_TO_SQL_TMPL,
#     prompt_type=PromptType.TEXT_TO_SQL,
# )

# sql_query_engine = NLSQLTableQueryEngine(
#     llm=LLamaIndexSettings.llm,
#     sql_database=sql_db,
#     text_to_sql_prompt=CUSTOM_TEXT_TO_SQL_PROMPT,
#     verbose=True,
#     synthesize_response=False,
# )


# if __name__ == "__main__":
#     res = sql_query_engine.query("find me contracts that end in dec 2025")
#     print("Response:", res)
#     print("Metadata:", res.metadata)
