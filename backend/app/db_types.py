# Generated using Supabase gen types CLI
from __future__ import annotations

import datetime
from typing import (
    Annotated,
    Literal,
    NotRequired,
    TypeAlias,
    TypedDict,
)

from pydantic import BaseModel, Field

AuthFactorType: TypeAlias = Literal["totp", "webauthn", "phone"]

AuthFactorStatus: TypeAlias = Literal["unverified", "verified"]

AuthAalLevel: TypeAlias = Literal["aal1", "aal2", "aal3"]

AuthCodeChallengeMethod: TypeAlias = Literal["s256", "plain"]

AuthOneTimeTokenType: TypeAlias = Literal[
    "confirmation_token",
    "reauthentication_token",
    "recovery_token",
    "email_change_token_new",
    "email_change_token_current",
    "phone_change_token",
]

AuthOauthRegistrationType: TypeAlias = Literal["dynamic", "manual"]

AuthOauthAuthorizationStatus: TypeAlias = Literal[
    "pending", "approved", "denied", "expired"
]

AuthOauthResponseType: TypeAlias = Literal["code"]

AuthOauthClientType: TypeAlias = Literal["public", "confidential"]

StorageBuckettype: TypeAlias = Literal["STANDARD", "ANALYTICS", "VECTOR"]

RealtimeEqualityOp: TypeAlias = Literal[
    "eq",
    "neq",
    "lt",
    "lte",
    "gt",
    "gte",
    "in",
    "like",
    "ilike",
    "is",
    "match",
    "imatch",
    "isdistinct",
]

RealtimeAction: TypeAlias = Literal["INSERT", "UPDATE", "DELETE", "TRUNCATE", "ERROR"]


class PublicPriceHistory(BaseModel):
    adjusted_close: float = Field(alias="adjusted_close")
    created_at: datetime.datetime = Field(alias="created_at")
    price_date: datetime.date = Field(alias="price_date")
    source: str = Field(alias="source")
    ticker: str = Field(alias="ticker")
    updated_at: datetime.datetime = Field(alias="updated_at")


class PublicPriceHistoryInsert(TypedDict):
    adjusted_close: Annotated[float, Field(alias="adjusted_close")]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias="created_at")]]
    price_date: Annotated[datetime.date, Field(alias="price_date")]
    source: NotRequired[Annotated[str, Field(alias="source")]]
    ticker: Annotated[str, Field(alias="ticker")]
    updated_at: NotRequired[Annotated[datetime.datetime, Field(alias="updated_at")]]


class PublicPriceHistoryUpdate(TypedDict):
    adjusted_close: NotRequired[Annotated[float, Field(alias="adjusted_close")]]
    created_at: NotRequired[Annotated[datetime.datetime, Field(alias="created_at")]]
    price_date: NotRequired[Annotated[datetime.date, Field(alias="price_date")]]
    source: NotRequired[Annotated[str, Field(alias="source")]]
    ticker: NotRequired[Annotated[str, Field(alias="ticker")]]
    updated_at: NotRequired[Annotated[datetime.datetime, Field(alias="updated_at")]]
