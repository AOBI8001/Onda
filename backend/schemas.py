from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Actor(BaseModel):
    id: str
    role: Literal["buyer", "seller"]
    merchant: str = "merchant-onda"


class ActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["cancel_order", "request_refund", "approve_refund", "reject_refund", "ship_order", "edit_product", "set_product_status", "close_ticket", "update_ticket", "plan_restock"]
    target: str = Field(min_length=1, max_length=80)
    params: dict = Field(default_factory=dict)
    expected_version: int | None = None


class ChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: bool


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    desc: str = Field(default="", max_length=500)
    price: float = Field(gt=0, le=100000, allow_inf_nan=False)
    stock: int = Field(ge=0, le=1000000)
    category: str = Field(min_length=1, max_length=60)


class FeedbackInput(BaseModel):
    rating: Literal["helpful", "unhelpful"]
    note: str = Field(default="", max_length=1000)
