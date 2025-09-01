from fastapi import APIRouter, Request
import httpx
from fastapi.responses import JSONResponse

router = APIRouter()

@router.post("/llm")
async def llm_proxy(request: Request):
    data = await request.json()
    llm_url = data.get("llm_url")
    api_key = data.get("api_key")
    payload = data.get("payload")

    if not llm_url or not payload:
        return JSONResponse(status_code=400, content={"error": "llm_url和payload不能为空"})

    headers = {
        "Content-Type": "application/json"
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(llm_url, json=payload, headers=headers)
        return JSONResponse(status_code=resp.status_code, content=resp.json()) 