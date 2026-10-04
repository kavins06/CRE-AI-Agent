"""Typed boundary for owner configuration; no provider credentials stored here."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RunnerID = Literal["codex", "fake", "claude_sdk", "openai_agents"]
RoleID = Literal["lead", "extraction", "verifier", "classifier", "reflection"]
Toggle = Literal["off", "ask", "on"]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonnegativeDecimal = Annotated[Decimal, Field(ge=0)]
Fraction = Annotated[Decimal, Field(ge=0, le=1)]
ROLES = frozenset({"lead", "extraction", "verifier", "classifier", "reflection"})


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RoleSettings(ConfigModel):
    runner: RunnerID
    profile: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")
    model: str = Field(min_length=1)

    @field_validator("model")
    @classmethod
    def nonblank_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model ID must not be blank")
        return value


class ModelsSettings(ConfigModel):
    runner: RunnerID
    roles: dict[RoleID, RoleSettings]

    @model_validator(mode="after")
    def complete_roles(self) -> Self:
        if set(self.roles) != ROLES:
            raise ValueError("All five runner roles must be configured")
        return self


class BudgetSettings(ConfigModel):
    segment_max_min: PositiveInt
    nightly_sessions: PositiveInt
    nightly_wallclock_h: PositiveInt
    max_parallel_extractions: PositiveInt
    max_parallel_sessions: PositiveInt
    codex_login_max_concurrency: Annotated[int, Field(strict=True, ge=1, le=1)]
    box_reconnect_s: PositiveInt


class GateSettings(ConfigModel):
    parity_abs: NonnegativeDecimal
    parity_rel: Fraction
    checksum_abs: NonnegativeDecimal
    number_abs: NonnegativeDecimal
    number_rel: Fraction
    fragility_margin: Annotated[Decimal, Field(gt=0, lt=1)]
    excel_functions: tuple[str, ...] = Field(min_length=1)

    @field_validator("excel_functions")
    @classmethod
    def valid_functions(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values) or not all(
            re.fullmatch(r"[A-Z][A-Z0-9.]*", value) for value in values
        ):
            raise ValueError("Excel whitelist must contain unique uppercase function names")
        return values


class ToggleSettings(ConfigModel):
    browse: Toggle = "off"
    licensed_data: Toggle = "off"
    email_brokers: Toggle = "off"
    send_loi: Toggle = "off"


class Settings(ConfigModel):
    models: ModelsSettings
    budget: BudgetSettings
    gates: GateSettings
    toggles: ToggleSettings
