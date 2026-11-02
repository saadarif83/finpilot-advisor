import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.identity import current_employee
from app.copilot import agent
from app.gateway.model_gateway import public_lane_info

router = APIRouter(prefix="/copilot", tags=["copilot"])


class ChatRequest(BaseModel):
    mode: str = "client"            # client | research
    client_id: str | None = None
    message: str
    history: list[dict] = []
    lane: str | None = None         # research mode only: "public" (default) or "private"


@router.get("/lanes")
def lanes(employee: dict = Depends(current_employee)):
    return public_lane_info()


@router.post("/stream")
async def stream(req: ChatRequest, employee: dict = Depends(current_employee)):
    async def gen():
        try:
            async for ev in agent.run(employee=employee, mode=req.mode, client_id=req.client_id, message=req.message,
                                      history=req.history, lane_requested=req.lane):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001 — never let the stream die silently on stage
            yield f"data: {json.dumps({'type': 'error', 'message': f'Copilot error: {e}'})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
