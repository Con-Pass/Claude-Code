from typing import Optional, Literal, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# Define valid status codes as a type alias for better OpenAI schema enforcement
ValidStatusCode = Literal[0, 1, 20, 21, 22, 23, 30, 31]


class MetadataStruct(BaseModel):
    """
    Structured metadata for contract search queries.
    All fields are optional, but at least one field should be populated for a valid search.

    Note: This model uses JSON Schema constraints (pattern, format) that OpenAI's
    structured output enforces at generation time, plus Pydantic validators as a safety net.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,  # Strip whitespace from strings
        validate_assignment=True,  # Validate on assignment
        extra="forbid",  # Forbid extra fields
    )

    company: Optional[List[str]] = Field(
        None,
        description="List of company names to search for",
        min_length=1,
        max_length=10,
    )
    # company_a: Optional[str] = Field(
    #     None,
    #     description="Company A name if multiple companies are mentioned",
    #     min_length=1,
    #     max_length=200,
    # )
    # company_b: Optional[str] = Field(
    #     None,
    #     description="Company B name if multiple companies are mentioned",
    #     min_length=1,
    #     max_length=200,
    # )
    # company_c: Optional[str] = Field(
    #     None,
    #     description="Company C name if multiple companies are mentioned",
    #     min_length=1,
    #     max_length=200,
    # )
    # company_d: Optional[str] = Field(
    #     None,
    #     description="Company D name if multiple companies are mentioned",
    #     min_length=1,
    #     max_length=200,
    # )
    title: Optional[str] = Field(
        None,
        description="Title of the contract if the user specifically mentions the title",
        min_length=1,
        max_length=200,
    )
    # status: Optional[str] = Field(
    #     None,
    #     description="Status of the contract if mentioned (comma-separated for multiple). Valid codes: 0 (DISABLE), 1 (ENABLE), 20 (IN_PROCESS), 21 (SIGNED), 22 (FINISH), 23 (SIGNED_BY_PAPER), 30 (CANCELED), 31 (EXPIRED)",
    #     pattern=r"^(0|1|20|21|22|23|30|31)(,\s*(0|1|20|21|22|23|30|31))*$",
    #     examples=["20", "21,22", "0,1,20"],
    # )
    contract_date_from: Optional[str] = Field(
        None,
        description="Contract date from in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    contract_date_to: Optional[str] = Field(
        None,
        description="Contract date to in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    contract_start_date_from: Optional[str] = Field(
        None,
        description="Contract start date from in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    contract_start_date_to: Optional[str] = Field(
        None,
        description="Contract start date to in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    contract_end_date_from: Optional[str] = Field(
        None,
        description="Contract end date from in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    contract_end_date_to: Optional[str] = Field(
        None,
        description="Contract end date to in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    cancel_notice_date_from: Optional[str] = Field(
        None,
        description="Cancel notice date from in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    cancel_notice_date_to: Optional[str] = Field(
        None,
        description="Cancel notice date to in YYYY-MM-DD format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",
        examples=["2025-01-01", "2025-12-31"],
    )
    court: Optional[str] = Field(
        None,
        description="Court of the contract if mentioned",
        min_length=1,
        max_length=500,
    )
    person_in_charge: Optional[str] = Field(
        None,
        description="Username of the person in charge of the contract if mentioned",
        min_length=1,
        max_length=200,
    )
    amount_from: Optional[str] = Field(
        None,
        description="Money amount from (numeric value without currency symbols)",
        pattern=r"^\d+(\.\d{1,2})?$",
        examples=["1000", "1000.50", "50000"],
    )
    amount_to: Optional[str] = Field(
        None,
        description="Money amount to (numeric value without currency symbols)",
        pattern=r"^\d+(\.\d{1,2})?$",
        examples=["5000", "5000.00", "100000"],
    )

    @field_validator(
        "contract_date_from",
        "contract_date_to",
        "contract_start_date_from",
        "contract_start_date_to",
        "contract_end_date_from",
        "contract_end_date_to",
        "cancel_notice_date_from",
        "cancel_notice_date_to",
        mode="after",
    )
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate that date fields follow YYYY-MM-DD format"""
        if v is None or v == "":
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format, got: {v}")

    # @field_validator("status", mode="after")
    # @classmethod
    # def validate_status(cls, v: Optional[str]) -> Optional[str]:
    #     """Validate that status contains valid status codes"""
    #     if v is None or v == "":
    #         return None

    #     valid_statuses = {"0", "1", "20", "21", "22", "23", "30", "31"}
    #     statuses = [s.strip() for s in v.split(",")]

    #     for status in statuses:
    #         if status and status not in valid_statuses:
    #             raise ValueError(
    #                 f"Invalid status code: {status}. Valid codes: {', '.join(sorted(valid_statuses))}"
    #             )

    #     return v

    @field_validator("amount_from", "amount_to", mode="before")
    @classmethod
    def validate_amount(cls, v: Optional[str]) -> Optional[str]:
        """
        Validate and clean amount fields.

        Note: The JSON Schema pattern should enforce numeric format at generation time,
        but this validator provides a safety net and cleans up any currency symbols
        that might slip through.
        """
        if v is None or v == "":
            return None

        # Remove common currency symbols and separators as a safety net
        cleaned = (
            v.replace(",", "")
            .replace("$", "")
            .replace("¥", "")
            .replace("€", "")
            .strip()
        )

        try:
            # Validate it's numeric
            float(cleaned)
            return cleaned
        except ValueError:
            raise ValueError(f"Amount must be numeric, got: {v}")

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "MetadataStruct":
        """
        Ensure at least one field is populated for a meaningful search.

        Note: This is a Python-side validation that runs AFTER OpenAI generates output.
        If the LLM generates an empty object, this will raise a ValidationError,
        which should be caught and handled by the calling code.
        """
        all_fields = self.model_dump(exclude_none=True)
        if not all_fields:
            raise ValueError(
                "At least one search field must be populated in MetadataStruct"
            )
        return self

    @model_validator(mode="after")
    def validate_date_ranges(self) -> "MetadataStruct":
        """
        Validate that 'from' dates are not after 'to' dates.

        Note: This is a Python-side validation that runs AFTER OpenAI generates output.
        The JSON Schema patterns enforce date format, but cannot enforce cross-field logic.
        """
        date_pairs = [
            ("contract_date_from", "contract_date_to"),
            ("contract_start_date_from", "contract_start_date_to"),
            ("contract_end_date_from", "contract_end_date_to"),
            ("cancel_notice_date_from", "cancel_notice_date_to"),
        ]

        for from_field, to_field in date_pairs:
            from_date = getattr(self, from_field)
            to_date = getattr(self, to_field)

            if from_date and to_date:
                try:
                    from_dt = datetime.strptime(from_date, "%Y-%m-%d")
                    to_dt = datetime.strptime(to_date, "%Y-%m-%d")

                    if from_dt > to_dt:
                        raise ValueError(
                            f"{from_field} ({from_date}) cannot be after {to_field} ({to_date})"
                        )
                except ValueError as e:
                    # Re-raise validation errors
                    if "cannot be after" in str(e):
                        raise

        return self

    @model_validator(mode="after")
    def validate_amount_range(self) -> "MetadataStruct":
        """
        Validate that amount_from is not greater than amount_to.

        Note: This is a Python-side validation that runs AFTER OpenAI generates output.
        The JSON Schema patterns enforce numeric format, but cannot enforce cross-field logic.
        """
        if self.amount_from and self.amount_to:
            try:
                from_amount = float(self.amount_from)
                to_amount = float(self.amount_to)

                if from_amount > to_amount:
                    raise ValueError(
                        f"amount_from ({self.amount_from}) cannot be greater than amount_to ({self.amount_to})"
                    )
            except ValueError as e:
                # Re-raise validation errors
                if "cannot be greater than" in str(e):
                    raise

        return self


class QueryToAPIParamsResponse(BaseModel):
    metadata: MetadataStruct
    feedback: str = Field(
        ...,
        description="Detailed message to the user about the field values. Do not use the word 'metadata' in the message.",
    )


class ContractToolResponse(BaseModel):
    contract_id: int
    name: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    companies_a: Optional[list[str]] = None
    companies_b: Optional[list[str]] = None
    companies_c: Optional[list[str]] = None
    companies_d: Optional[list[str]] = None
    end_date: Optional[str] = None
    notice_date: Optional[str] = None
    contract_date: Optional[str] = None
    start_date: Optional[str] = None
    amount: Optional[str] = None
    court: Optional[str] = None
    contract_type: Optional[str] = None
    status: Optional[str] = None
    auto_update: Optional[str] = None
    antisocial: Optional[str] = None


# ---------- Clause-Level Risk ----------
class ClauseRisk(BaseModel):
    clause: str = Field(
        ..., description="Clause or section identifier, e.g., '8.1 Termination'"
    )
    snippet: Optional[str] = Field(
        None, description="Extracted text snippet from the clause"
    )
    risk_type: Literal[
        "Legal", "Financial", "Operational", "Compliance", "Reputational", "Strategic"
    ] = Field(..., description="Type/category of the risk")
    description: str = Field(..., description="Description of the risk identified")
    likelihood: Literal["Low", "Medium", "High"] = Field(
        ..., description="Probability of occurrence"
    )
    impact: Literal["Low", "Medium", "High"] = Field(
        ..., description="Severity of impact"
    )
    risk_level: Literal["Low", "Medium", "High", "Critical"] = Field(
        ..., description="Overall risk severity"
    )
    recommendation: Optional[str] = Field(
        None, description="Recommended mitigation or negotiation action"
    )
    confidence_score: Optional[float] = Field(
        None, ge=0, le=1, description="AI confidence score (0-1)"
    )


# ---------- Risk Category Summary ----------
class RiskCategorySummary(BaseModel):
    category: Literal[
        "Legal", "Financial", "Operational", "Compliance", "Reputational", "Strategic"
    ]
    summary: Optional[str] = None
    example_risks: Optional[List[str]] = None


# ---------- Contract Metadata ----------
class ContractMetadata(BaseModel):
    contract_id: Optional[str] = None
    contract_name: str
    parties: List[str]
    created_date: Optional[datetime] = None
    effective_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    jurisdiction: Optional[str] = None


# ---------- Contract Summary ----------
class ContractSummary(BaseModel):
    purpose: Optional[str] = Field(..., description="Purpose of the contract")
    key_obligations: Optional[List[str]] = Field(
        ..., description="Key obligations of the contract"
    )


# ---------- Full Risk Analysis ----------
class RiskAnalysis(BaseModel):
    contract_id: int
    contract_name: str
    parties: List[str] = Field(..., description="Parties involved in the contract")
    summary: Optional[ContractSummary] = None
    risks: List[ClauseRisk]
    category_summary: Optional[List[RiskCategorySummary]] = None
    overall_risk_rating: Literal["Low", "Medium", "High", "Critical"]
    summary_comment: Optional[str] = Field(
        ..., description="Summary comment of the risk analysis"
    )
    high_risk_clauses: Optional[List[str]] = Field(
        ..., description="High risk clauses of the contract"
    )
    next_steps: Optional[str] = Field(
        ..., description="Next steps for the risk analysis"
    )


# class FetchContractBodyResponse(BaseModel):
#     status: Literal["success", "error"]
#     description: Optional[str] = None
#     contract_body: Optional[str] = None
