from datetime import date

from usage_statement.statement_service import (
    AppointmentEvent,
    StatementRequest,
    decide_statement,
    send_monthly_statement,
)


class RecordingInfrai:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def account_usage(self):
        self.calls.append("account.usage")
        return {"period_total": 17}

    def generate_pdf(self, markdown: str, operation_id: str):
        self.calls.append("pdf.generate")
        assert "Completed: 2" in markdown
        assert "appt-100" not in markdown
        return {"url": "https://downloads.example/statement.pdf"}

    def send_email(self, to: str, subject: str, html: str, operation_id: str):
        self.calls.append("email.send")
        assert "https://downloads.example/statement.pdf" in html
        return {"message_id": "msg_123"}


def make_request(statuses: list[str]) -> StatementRequest:
    return StatementRequest(
        customer_account_ref="clinic-west",
        recipient_email="operations@example.com",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        appointments=[
            AppointmentEvent(appointment_ref=f"appt-{100 + index}", status=status)
            for index, status in enumerate(statuses)
        ],
    )


def test_completed_appointments_create_patient_safe_statement_and_handoff():
    infrai = RecordingInfrai()

    result = send_monthly_statement(
        make_request(["completed", "cancelled", "completed"]), infrai
    )

    assert result.status == "sent"
    assert result.billable_appointments == 2
    assert result.message_id == "msg_123"
    assert infrai.calls == ["account.usage", "pdf.generate", "email.send"]


def test_non_billable_month_skips_external_delivery():
    request = make_request(["cancelled", "no_show"])
    infrai = RecordingInfrai()

    assert decide_statement(request.appointments).should_send is False
    result = send_monthly_statement(request, infrai)

    assert result.status == "skipped"
    assert infrai.calls == []
