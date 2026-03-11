from datetime import datetime
from typing import Any, Mapping
from llama_index.llms.openai import OpenAI
from app.core.config import settings
from llama_index.core.tools import FunctionTool
from app.core.logging_config import get_logger
from app.schemas.chat import SessionType
from app.schemas.contract_tools import (
    ContractToolResponse,
    MetadataStruct,
    RiskAnalysis,
    QueryToAPIParamsResponse,
)
from urllib.parse import unquote
from app.schemas.general import GeneralResponse
from app.services.chatbot.tools.tool_prompts import (
    QUERY_TO_API_PARAMS_PROMPT_TEMPLATE,
    RISK_ANALYSIS_PROMPT_TEMPLATE,
)

# from app.schemas.contract_tools import FetchContractBodyResponse
from app.services.conpass_api_service import get_conpass_api_service, ConpassApiService
from app.utils.contract_tool_utils import (
    get_contract_status_map,
    get_auto_update_map,
    get_antisocial_map,
)


logger = get_logger(__name__)

MAX_CONTRACTS_TO_ANALYZE = 2
MAX_CONTRACTS_TO_READ = 4


class ContractTools:
    def __init__(self, conpass_api_service: ConpassApiService):
        self.openai_api_key = settings.OPENAI_API_KEY
        self.sllm_model = "gpt-4.1-mini"
        self.sllm_temperature = 0.3
        self.conpass_api_service = conpass_api_service

    def _map_to_django_params(self, api_params: Mapping[str, Any]) -> dict:
        django_params = {
            "page": 1,
            "type": 1,
        }
        django_params["company"] = api_params.get("company", "")
        django_params["default2"] = api_params.get("company_a", "")
        django_params["default3"] = api_params.get("company_b", "")
        django_params["default4"] = api_params.get("company_c", "")
        django_params["default5"] = api_params.get("company_d", "")
        django_params["default1"] = api_params.get("title", "")
        django_params["status"] = api_params.get("status", "")
        django_params["defaultDateFrom10"] = api_params.get(
            "cancel_notice_date_from", ""
        )
        django_params["defaultDateTo10"] = api_params.get("cancel_notice_date_to", "")
        django_params["default14"] = api_params.get("court", "")
        django_params["default17"] = api_params.get("person_in_charge", "")
        django_params["defaultFrom19"] = api_params.get("amount_from", "")
        django_params["defaultTo19"] = api_params.get("amount_to", "")
        django_params["defaultDateFrom6"] = api_params.get("contract_date_from", "")
        django_params["defaultDateTo6"] = api_params.get("contract_date_to", "")
        django_params["defaultDateFrom7"] = api_params.get(
            "contract_start_date_from", ""
        )
        django_params["defaultDateTo7"] = api_params.get("contract_start_date_to", "")
        django_params["defaultDateFrom8"] = api_params.get("contract_end_date_from", "")
        django_params["defaultDateTo8"] = api_params.get("contract_end_date_to", "")
        return django_params

    async def _query_to_api_params(self, user_query: str) -> GeneralResponse:
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            prompt = QUERY_TO_API_PARAMS_PROMPT_TEMPLATE.format(
                today=today, query=user_query
            )

            llm = OpenAI(
                model=self.sllm_model,
                temperature=self.sllm_temperature,
                api_key=self.openai_api_key,
            )

            sllm = llm.as_structured_llm(QueryToAPIParamsResponse)

            response = await sllm.acomplete(prompt)

            res_data = response.model_dump().get("raw", {})

            return GeneralResponse(
                status="success",
                description="Query to API params performed successfully",
                data=res_data,
            )
        except Exception:
            logger.exception(f"Error converting user query to API params: {user_query}")
            return GeneralResponse(
                status="error",
                description=f"Error converting user query to API params: {user_query}",
            )

    async def contract_fetch_tool(
        self, api_params: MetadataStruct, number_of_contracts_to_fetch: int = 100
    ) -> dict:
        logger.info(
            f"Calling contract_fetch_tool with api_params: {api_params} and number_of_contracts_to_fetch: {number_of_contracts_to_fetch}"
        )
        try:
            # Convert dict to MetadataStruct for validation and processing
            try:
                if isinstance(api_params, MetadataStruct):
                    metadata_struct = api_params
                else:
                    metadata_struct = MetadataStruct(**api_params)
            except Exception as e:
                logger.error(f"Error creating MetadataStruct from api_params: {e}")
                return {
                    "feedback": f"Incorrect API params: {api_params}",
                    "contracts": [],
                    "number_of_contracts": 0,
                }

            filtered_api_params = {
                key: value
                for key, value in metadata_struct.model_dump().items()
                if value is not None and value != ""
            }
            logger.info(f"filtered_api_params: {filtered_api_params}")

            # Handle multiple companies by making separate API calls for each
            all_contracts = []
            all_contract_ids = set()  # To avoid duplicates

            if metadata_struct.company and len(metadata_struct.company) > 0:
                # Multiple companies - make separate calls for each
                companies = [
                    company.strip()
                    for company in metadata_struct.company
                    if company.strip()
                ]
                logger.info(f"Companies to search: {companies}")

                for company in companies:
                    # Create a copy of metadata_struct with single company
                    single_company_params = metadata_struct.model_copy()
                    single_company_params.company = [company]  # Single company as list

                    single_company_params_dict: dict[str, Any] = (
                        single_company_params.model_dump()
                    )

                    django_params = self._map_to_django_params(
                        single_company_params_dict
                    )
                    logger.info(
                        f"Fetching contracts for company '{company}' with params: {django_params}"
                    )

                    conpass_api_response = await self.conpass_api_service.get_contracts(
                        django_params, number_of_contracts_to_fetch
                    )

                    if conpass_api_response.status == "error":
                        logger.warning(
                            f"Error fetching contracts for company '{company}': {conpass_api_response.description}"
                        )
                        continue

                    conpass_api_results = conpass_api_response.data.get("results", [])
                    logger.info(
                        f"Found {len(conpass_api_results)} contracts for company '{company}'"
                    )

                    # Process contracts and add to combined results
                    for result in conpass_api_results:
                        contract_id = result.get("id")
                        if contract_id in all_contract_ids:
                            continue  # Skip duplicates
                        all_contract_ids.add(contract_id)

                        url = f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}"
                        contract_status = get_contract_status_map(
                            result.get("status", None)
                        )
                        auto_update = get_auto_update_map(
                            result.get("autoUpdate", None)
                        )
                        antisocial = get_antisocial_map(result.get("antisocial", None))
                        contract = ContractToolResponse(
                            contract_id=contract_id,
                            name=result.get("name", None),
                            title=result.get("title", None),
                            companies_a=result.get("companiesA", None),
                            companies_b=result.get("companiesB", None),
                            companies_c=result.get("companiesC", None),
                            companies_d=result.get("companiesD", None),
                            end_date=result.get("endDate", None),
                            notice_date=result.get("noticeDate", None),
                            contract_date=result.get("contractDate", None),
                            start_date=result.get("startDate", None),
                            amount=result.get("amount", None),
                            court=result.get("cort", None),
                            contract_type=result.get("contractType", None),
                            status=contract_status,
                            auto_update=auto_update,
                            antisocial=antisocial,
                            url=url,
                        )
                        all_contracts.append(contract.model_dump())
            else:
                django_params = self._map_to_django_params(metadata_struct.model_dump())
                logger.info(f"Params: {django_params}")

                conpass_api_response = await self.conpass_api_service.get_contracts(
                    django_params, number_of_contracts_to_fetch
                )
                if conpass_api_response.status == "error":
                    logger.warning(
                        f"Error fetching contracts by params: {django_params} and number_of_contracts_to_fetch: {number_of_contracts_to_fetch}: {conpass_api_response.description}"
                    )
                    return {
                        "feedback": conpass_api_response.description,
                        "contracts": [],
                        "number_of_contracts": 0,
                    }
                conpass_api_results = conpass_api_response.data.get("results", [])

                if not conpass_api_results:
                    logger.warning(
                        f"No contracts found for the given query and number_of_contracts_to_fetch: {number_of_contracts_to_fetch}"
                    )
                    return {
                        "feedback": "No contracts found for the given query. ",
                        "contracts": [],
                        "number_of_contracts": 0,
                    }

                for result in conpass_api_results:
                    contract_id = result.get("id")
                    url = f"{settings.CONPASS_FRONTEND_BASE_URL}/contract/{contract_id}"
                    contract_status = get_contract_status_map(
                        result.get("status", None)
                    )
                    auto_update = get_auto_update_map(result.get("autoUpdate", None))
                    antisocial = get_antisocial_map(result.get("antisocial", None))
                    contract = ContractToolResponse(
                        contract_id=contract_id,
                        name=result.get("name", None),
                        title=result.get("title", None),
                        companies_a=result.get("companiesA", None),
                        companies_b=result.get("companiesB", None),
                        companies_c=result.get("companiesC", None),
                        companies_d=result.get("companiesD", None),
                        end_date=result.get("endDate", None),
                        notice_date=result.get("noticeDate", None),
                        contract_date=result.get("contractDate", None),
                        start_date=result.get("startDate", None),
                        amount=result.get("amount", None),
                        court=result.get("cort", None),
                        contract_type=result.get("contractType", None),
                        status=contract_status,
                        auto_update=auto_update,
                        antisocial=antisocial,
                        url=url,
                    )
                    all_contracts.append(contract.model_dump())

            if not all_contracts:
                logger.warning(
                    f"No contracts found for the given api params: {api_params} and number_of_contracts_to_fetch: {number_of_contracts_to_fetch}"
                )
                return {
                    "feedback": f"No contracts found with the given api params: {api_params}",
                    "contracts": [],
                    "number_of_contracts": 0,
                }

            return {
                "feedback": f"Contracts fetched successfully with the given api params: {api_params}",
                "filter_params": filtered_api_params,
                "contracts": all_contracts,
                "number_of_contracts": len(all_contracts),
            }

        except Exception:
            logger.exception(
                f"Error fetching contracts for api params: {api_params} and number_of_contracts_to_fetch: {number_of_contracts_to_fetch}"
            )
            return {
                "feedback": f"Error while fetching contracts with the given api params: {api_params}",
                "contracts": [],
                "number_of_contracts": 0,
            }

    async def _perform_risk_analysis(self, body_decoded: str) -> GeneralResponse:
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            prompt = RISK_ANALYSIS_PROMPT_TEMPLATE.format(
                today=today, contract_body=body_decoded
            )

            llm = OpenAI(
                model=self.sllm_model,
                temperature=self.sllm_temperature,
                api_key=self.openai_api_key,
            )

            sllm = llm.as_structured_llm(RiskAnalysis)

            response = await sllm.acomplete(prompt)

            res_data = response.model_dump().get("raw", {})
            return GeneralResponse(
                status="success",
                description="Risk analysis performed successfully",
                data=res_data,
            )
        except Exception:
            logger.exception("Error performing risk analysis")
            return GeneralResponse(
                status="error",
                description="Error performing risk analysis",
            )

    async def _fetch_contract_body(self, contract_id: int) -> GeneralResponse:
        try:
            conpass_api_response = await self.conpass_api_service.get_contract_body(
                contract_id
            )
            if conpass_api_response.status == "error":
                logger.warning(
                    f"Error fetching contract body for contract {contract_id}: {conpass_api_response.description}"
                )
                return GeneralResponse(
                    status="error",
                    description=conpass_api_response.description,
                )
            conpass_api_results = conpass_api_response.data.get("response", [])
            if not conpass_api_results:
                logger.warning(
                    f"No contract body found for contract {contract_id}: {conpass_api_response.description}"
                )
                return GeneralResponse(
                    status="error",
                    description=f"No contract body found for contract {contract_id}",
                )
            contract_body = conpass_api_results[0].get("body", {}).get("body", "")
            body_decoded = unquote(contract_body)
            return GeneralResponse(status="success", data=body_decoded)
        except Exception:
            logger.exception(f"Error fetching contract body for contract {contract_id}")
            return GeneralResponse(
                status="error",
                description=f"Error fetching contract body for contract {contract_id}",
            )

    async def risk_analysis_tool(self, contract_ids: list[int]) -> list[dict]:
        if len(contract_ids) > MAX_CONTRACTS_TO_ANALYZE:
            return [
                {
                    "summary_comment": f"Error: You can only analyze up to {MAX_CONTRACTS_TO_ANALYZE} contracts at a time.",
                }
            ]
        logger.info(f"Calling risk_analysis_tool with contract_ids: {contract_ids}")
        risk_analysis_list = []
        for contract_id in contract_ids:
            try:
                contract_body_response = await self._fetch_contract_body(contract_id)
                if contract_body_response.status == "error":
                    logger.warning(
                        f"Error fetching contract body for contract {contract_id}: {contract_body_response.description}"
                    )
                    risk_analysis_list.append(
                        {
                            "contract_id": contract_id,
                            "summary_comment": contract_body_response.description,
                        }
                    )
                    continue
                risk_analysis = await self._perform_risk_analysis(
                    contract_body_response.data
                )
                if risk_analysis.status == "error":
                    logger.warning(
                        f"Error performing risk analysis for contract {contract_id}: {risk_analysis.description}"
                    )
                    risk_analysis_list.append(
                        {
                            "contract_id": contract_id,
                            "summary_comment": risk_analysis.description,
                        }
                    )
                    continue
                risk_analysis_data = risk_analysis.data if risk_analysis.data else {}
                risk_analysis_data["contract_id"] = contract_id
                risk_analysis_list.append(risk_analysis_data)
                logger.info(
                    f"Risk analysis for contract {contract_id} performed successfully"
                )
            except Exception:
                logger.exception(
                    f"Error performing risk analysis for contract {contract_id}"
                )
                risk_analysis_list.append(
                    {
                        "contract_id": contract_id,
                        "summary_comment": f"Error performing risk analysis for contract {contract_id}",
                    }
                )

        return risk_analysis_list

    async def read_contracts_tool(self, contract_ids: list[int]) -> list[dict]:
        logger.info(f"Calling read_contracts_tool with contract_ids: {contract_ids}")
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
                contract_body_response = await self._fetch_contract_body(contract_id)

                if contract_body_response.status == "error":
                    logger.warning(
                        f"Error fetching contract body for contract {contract_id}: {contract_body_response.description}"
                    )
                    contracts.append(
                        {
                            "contract_id": contract_id,
                            "error_message": contract_body_response.description,
                        }
                    )
                    continue
                contract_body = contract_body_response.data
                contracts.append(
                    {
                        "contract_id": contract_id,
                        "contract_body": contract_body,
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


def get_contract_tools(
    conpass_jwt: str, user_query: str, session_type: SessionType
) -> list[FunctionTool]:
    conpass_api_service = get_conpass_api_service(conpass_jwt=conpass_jwt)
    tool = ContractTools(conpass_api_service=conpass_api_service)

    today = datetime.now().strftime("%Y-%m-%d")

    if session_type == SessionType.CONPASS_ONLY:
        return [
            FunctionTool.from_defaults(
                async_fn=tool.contract_fetch_tool,
                name="contract_fetch_tool",
                description=f"""
                    Today's date is {today}.

                    Use this tool to retrieve contract metadata when a contract ID is not provided. Do not use this tool if a contract ID is explicitly mentioned — use the read_contracts_tool instead.

                    This tool supports searching and filtering by multiple optional fields. Extract only what the user explicitly states; do not invent values. If the user refers to a contract "renewal date", interpret that as the contract end date. Do not ask the user too many questions for clarification.


                    COMPLEX QUERIES — CALL MULTIPLE TIMES
                    - For comparisons or multi-part questions, call this tool multiple times with different parameters
                    - Start broad, inspect results, then issue follow-up calls to narrow down
                    - When comparing groups (different periods, companies, or statuses), make separate calls per group and synthesize

                    EXAMPLES
                    1) "Compare signed contracts in Q1 vs Q2 2024"
                    → Call A: status=21, contract_date_from=2024-01-01, contract_date_to=2024-03-31
                    → Call B: status=21, contract_date_from=2024-04-01, contract_date_to=2024-06-30
                    → Compare result sets

                    2) "Find high-value contracts expiring soon"
                    → Call A: contract_end_date_from=<start>, contract_end_date_to=<end>
                    → Call B (optional refinement): amount_from=<threshold>

                    3) "Show all Company X contracts, then which are expired"
                    → Call A: company=Company X
                    → Call B: company=Company X, status=31

                    Return contracts that match the user's criteria. Prefer multiple smaller, focused calls over one overly broad call when the query is complex.
                """,
            ),
            FunctionTool.from_defaults(
                async_fn=tool.read_contracts_tool,
                name="read_contracts_tool",
                description=f"""
                Today's date is {today}.

                Use this tool when you need to read the text of the contracts, for example, when the user asks to explain the contracts. This tool takes a list of contract IDs as input and returns a text of the contracts. This tool can be used to fetch the text of the contracts based on the contract ID.
                """,
            ),
        ]
    else:
        return [
            FunctionTool.from_defaults(
                async_fn=tool.contract_fetch_tool,
                name="contract_fetch_tool",
                description=f"""
                    Today's date is {today}.

                    Use this tool to retrieve contract metadata when a contract ID is not provided. Do not use this tool if a contract ID is explicitly mentioned — use the read_contracts_tool instead.

                    This tool supports searching and filtering by multiple optional fields. Extract only what the user explicitly states; do not invent values. If the user refers to a contract "renewal date", interpret that as the contract end date. Do not ask the user too many questions for clarification.


                    COMPLEX QUERIES — CALL MULTIPLE TIMES
                    - For comparisons or multi-part questions, call this tool multiple times with different parameters
                    - Start broad, inspect results, then issue follow-up calls to narrow down
                    - When comparing groups (different periods, companies, or statuses), make separate calls per group and synthesize

                    EXAMPLES
                    1) "Compare signed contracts in Q1 vs Q2 2024"
                    → Call A: status=21, contract_date_from=2024-01-01, contract_date_to=2024-03-31
                    → Call B: status=21, contract_date_from=2024-04-01, contract_date_to=2024-06-30
                    → Compare result sets

                    2) "Find high-value contracts expiring soon"
                    → Call A: contract_end_date_from=<start>, contract_end_date_to=<end>
                    → Call B (optional refinement): amount_from=<threshold>

                    3) "Show all Company X contracts, then which are expired"
                    → Call A: company=Company X
                    → Call B: company=Company X, status=31

                    Return contracts that match the user's criteria. Prefer multiple smaller, focused calls over one overly broad call when the query is complex.
                """,
            ),
            FunctionTool.from_defaults(
                async_fn=tool.risk_analysis_tool,
                name="risk_analysis_tool",
                description=f"""
                Today's date is {today}.

                Use this tool when the user asks for the risk analysis of multiple contracts. The tool returns the risk analysis of the contracts. This tool takes a list of contract IDs as input and returns a list of risk analysis for each contract. Your risk analysis should be in a well formatted and easy to read markdown format with line breaks between each contract, proper headings and subheadings, and proper formatting of the text.
                """,
            ),
            FunctionTool.from_defaults(
                async_fn=tool.read_contracts_tool,
                name="read_contracts_tool",
                description=f"""
                Today's date is {today}.

                Use this tool when you need to read the text of the contracts, for example, when the user asks to explain the contracts. This tool takes a list of contract IDs as input and returns a text of the contracts. This tool can be used to fetch the text of the contracts based on the contract ID.
                """,
            ),
        ]


# import asyncio
# import os

# tool = ContractTools(conpass_jwt=os.getenv("CONPASS_JWT"))
# print(asyncio.run(tool.risk_analysis_tool([5512, 5071, 5065, 5058, 5051])))
