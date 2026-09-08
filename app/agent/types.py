"""Validated application responses and provider-neutral conversation types."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr, model_validator

NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=1, pattern=r"\S")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Record(StrictModel):
    played: NonnegativeInt
    wins: NonnegativeInt
    draws: NonnegativeInt
    losses: NonnegativeInt

    @model_validator(mode="after")
    def totals_match(self) -> "Record":
        if self.played != self.wins + self.draws + self.losses:
            raise ValueError("Played must equal wins + draws + losses")
        return self


class ComparisonItem(StrictModel):
    label: Text
    value: Number


class Comparison(StrictModel):
    metric: Text
    items: list[ComparisonItem] = Field(min_length=2)
    winner_labels: list[Text]

    @model_validator(mode="after")
    def winners_match(self) -> "Comparison":
        labels = [item.label for item in self.items]
        maximum = max(item.value for item in self.items)
        winners = {item.label for item in self.items if item.value == maximum}
        if len(set(labels)) != len(labels):
            raise ValueError("Comparison labels must be unique")
        if set(self.winner_labels) != winners or len(self.winner_labels) != len(winners):
            raise ValueError("Winner labels must include exactly all items tied for maximum")
        return self


class Fixture(StrictModel):
    match_id: Text
    date: date
    home_team: Text
    away_team: Text
    home_goals: NonnegativeInt
    away_goals: NonnegativeInt


class Answered(StrictModel):
    status: Literal["answered"]


class CountAnswer(Answered):
    kind: Literal["count"]
    value: NonnegativeInt


class AverageAnswer(Answered):
    kind: Literal["average"]
    value: Number


class RecordAnswer(Answered):
    kind: Literal["record"]
    value: Record


class ComparisonAnswer(Answered):
    kind: Literal["comparison"]
    value: Comparison


class HeadToHeadAnswer(Answered):
    kind: Literal["head_to_head"]
    value: list[Fixture]


class ExactAnswer(Answered):
    kind: Literal["exact"]
    value: StrictStr | StrictBool


class UnsupportedAnswer(StrictModel):
    status: Literal["unsupported"]
    reason: Text


SupportedAnswer = Annotated[
    CountAnswer | AverageAnswer | RecordAnswer | ComparisonAnswer | HeadToHeadAnswer | ExactAnswer,
    Field(discriminator="kind"),
]
StructuredAnswer = Annotated[SupportedAnswer | UnsupportedAnswer, Field(discriminator="status")]


class AskRequest(StrictModel):
    question: Text = Field(max_length=10000)


class FinalAnswer(StrictModel):
    answer: Text
    structured_answer: StructuredAnswer


class TokenUsage(StrictModel):
    input_tokens: NonnegativeInt
    output_tokens: NonnegativeInt


class ToolCall(StrictModel):
    name: Text
    arguments: dict
    call_id: Text


class ToolExecution(StrictModel):
    call_id: str
    name: str
    requested_arguments: dict
    validated_arguments: dict | None = None
    status: Literal["success", "validation_error", "tool_error"]
    result: dict | None = None
    error: dict | None = None


class AskResponse(FinalAnswer):
    tool_trace: list[ToolExecution]
    tool_calls: list[ToolCall]
    evidence: list[str]
    model: str
    usage: TokenUsage | None
    latency_ms: float = Field(ge=0, allow_inf_nan=False)


class ToolDefinition(StrictModel):
    name: str
    description: str
    parameters: dict


class ToolReply(StrictModel):
    call_id: str
    content: dict
    is_error: bool = False


class Message(StrictModel):
    role: Literal["user", "assistant"]
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolReply] = Field(default_factory=list)


class ModelResponse(StrictModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage | None = None
    stop_reason: Literal["end_turn", "tool_use"]
