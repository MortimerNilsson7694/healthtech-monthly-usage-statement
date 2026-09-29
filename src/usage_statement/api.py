from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException

from .infrai_client import InfraiClient, InfraiError
from .statement_service import StatementRequest, StatementResult, send_monthly_statement

app = FastAPI(title="Healthtech usage statement service")


def get_infrai() -> InfraiClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")
    return InfraiClient(api_key=api_key)


@app.post("/statements/monthly", response_model=StatementResult)
def create_monthly_statement(
    request: StatementRequest, infrai: InfraiClient = Depends(get_infrai)
) -> StatementResult:
    try:
        return send_monthly_statement(request, infrai)
    except InfraiError as exc:
        status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    finally:
        infrai.close()
