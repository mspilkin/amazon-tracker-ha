from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal[
    "placed",
    "preparing",
    "shipped",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "returned",
    "unknown",
]

ReturnStatus = Literal[
    "requested", "shipped_back", "received", "refunded", "denied", "unknown"
]

RefundStatus = Literal["pending", "issued", "denied", "unknown"]


class Item(BaseModel):
    asin: str | None = None
    title: str
    thumbnail_url: str | None = None
    quantity: int = 1
    unit_price: float | None = None
    category: str | None = None


class TrackingEvent(BaseModel):
    event_time: datetime
    location: str | None = None
    description: str


class Order(BaseModel):
    order_id: str
    order_date: date
    total_amount: float
    currency: str
    payment_method: str | None = None
    status: OrderStatus = "unknown"
    raw_status_text: str | None = None
    carrier: str | None = None
    tracking_number: str | None = None
    eta_date: date | None = None
    delivered_at: datetime | None = None
    delivery_photo_url: str | None = None
    items: list[Item] = Field(default_factory=list)
    tracking_events: list[TrackingEvent] = Field(default_factory=list)


class ReturnRecord(BaseModel):
    order_id: str
    item_title: str | None = None
    return_status: ReturnStatus = "unknown"
    refund_amount: float | None = None
    refund_status: RefundStatus = "unknown"
    updated_at: datetime


class ScrapeResult(BaseModel):
    outcome: Literal["success", "partial", "login_required", "error"]
    orders_seen: int = 0
    orders_changed: int = 0
    orders: list[Order] = Field(default_factory=list)
    returns: list[ReturnRecord] = Field(default_factory=list)
    error_message: str | None = None
    selector_version: str | None = None


class ScrapeRequest(BaseModel):
    since: date | None = None
    active_order_ids: list[str] = Field(default_factory=list)
    history_months: int | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "starting", "error"] = "ok"
    logged_in: bool
    amazon_domain: str
    browser_ready: bool
    last_scrape_at: datetime | None = None
    login_in_progress: bool = False


class LoginOpenResponse(BaseModel):
    status: Literal["opened", "already_open"]
    novnc_path: str


class SimpleStatus(BaseModel):
    status: str
    message: str | None = None
