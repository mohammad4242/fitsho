from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse

from .schemas import ErrorCode, ErrorDetail, ErrorEnvelope


@dataclass
class AgentServiceError(Exception):
    code: ErrorCode
    message: str
    status_code: int = 400


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid4())


async def handle_service_error(request: Request, exc: AgentServiceError) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            request_id=request_id(request),
        )
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))
