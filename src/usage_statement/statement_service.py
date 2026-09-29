from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from html import escape
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .infrai_client import InfraiClient


class AppointmentEvent(BaseModel):
    appointment_ref: str = Field(min_length=1, max_length=80)
    status: Literal["completed", "cancelled", "no_show"]


class StatementRequest(BaseModel):
    customer_account_ref: str = Field(min_length=1, max_length=80)
    recipient_email: str = Field(min_length=3, max_length=254)
    period_start: date
    period_end: date
    appointments: list[AppointmentEvent]

    @model_validator(mode="after")
    def dates_are_a_closed_month(self) -> "StatementRequest":
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        local, separator, domain = self.recipient_email.rpartition("@")
        if not separator or not local or "." not in domain:
            raise ValueError("recipient_email must be an email address")
        return self


class StatementResult(BaseModel):
    statement_ref: str
    status: Literal["sent", "skipped"]
    billable_appointments: int
    pdf_url: str | None = None
    message_id: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StatementDecision:
    billable: int
    cancelled: int
    no_show: int

    @property
    def should_send(self) -> bool:
        return self.billable > 0


def decide_statement(events: list[AppointmentEvent]) -> StatementDecision:
    return StatementDecision(
        billable=sum(event.status == "completed" for event in events),
        cancelled=sum(event.status == "cancelled" for event in events),
        no_show=sum(event.status == "no_show" for event in events),
    )


def send_monthly_statement(
    request: StatementRequest, infrai: InfraiClient
) -> StatementResult:
    decision = decide_statement(request.appointments)
    statement_ref = _statement_ref(request)
    if not decision.should_send:
        return StatementResult(
            statement_ref=statement_ref,
            status="skipped",
            billable_appointments=0,
            reason="No completed appointments in this period",
        )

    usage = infrai.account_usage()
    markdown = _statement_markdown(request, decision, usage, statement_ref)
    pdf = infrai.generate_pdf(markdown, statement_ref)
    pdf_url = str(pdf["url"])
    email = infrai.send_email(
        to=str(request.recipient_email),
        subject=f"Usage statement {request.period_start:%Y-%m}",
        html=(
            f"<p>Your monthly operational usage statement is ready.</p>"
            f'<p><a href="{escape(pdf_url)}">Download statement {escape(statement_ref)}</a></p>'
        ),
        operation_id=statement_ref,
    )
    return StatementResult(
        statement_ref=statement_ref,
        status="sent",
        billable_appointments=decision.billable,
        pdf_url=pdf_url,
        message_id=str(email["message_id"]),
    )


def _statement_ref(request: StatementRequest) -> str:
    identity = f"{request.customer_account_ref}:{request.period_start}:{request.period_end}"
    return f"stmt-{sha256(identity.encode()).hexdigest()[:12]}"


def _statement_markdown(
    request: StatementRequest,
    decision: StatementDecision,
    usage: dict[str, Any],
    statement_ref: str,
) -> str:
    return "\n".join(
        [
            "# Monthly appointment usage statement",
            "",
            f"Statement reference: {statement_ref}",
            f"Customer account: {request.customer_account_ref}",
            f"Period: {request.period_start.isoformat()} through {request.period_end.isoformat()}",
            "",
            "## Appointment workflow totals",
            f"- Completed: {decision.billable}",
            f"- Cancelled: {decision.cancelled}",
            f"- No-show: {decision.no_show}",
            "",
            "## Account usage recorded by Infrai",
            f"```json\n{_compact_usage(usage)}\n```",
            "",
            "Appointment references and patient details are intentionally omitted.",
        ]
    )


def _compact_usage(usage: dict[str, Any]) -> str:
    import json

    return json.dumps(usage, sort_keys=True, separators=(",", ":"), default=str)
