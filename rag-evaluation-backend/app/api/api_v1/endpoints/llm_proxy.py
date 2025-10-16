from fastapi import APIRouter, Request, HTTPException
import httpx
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

router = APIRouter()

class LLMTestRequest(BaseModel):
    base_url: str
    api_key: str
    model_name: str
    additional_params: Optional[Dict[str, Any]] = None

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

@router.post("/llm/test")
async def test_llm_connection(request: LLMTestRequest):
    """测试LLM连接是否正常"""
    try:
        headers = {
            "Content-Type": "application/json"
        }
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        # 构建测试消息
        payload = {
            "model": request.model_name,
            "messages": [
                {"role": "system", "content": "你是一个有帮助的AI助手。"},
                {"role": "user", "content": "你好"}
            ],
            "temperature": 0.1,
            "max_tokens": 50
        }
        
        # 合并额外参数
        if request.additional_params:
            payload.update(request.additional_params)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{request.base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "message": "连接成功",
                    "response": content[:100] + "..." if len(content) > 100 else content
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                return {
                    "success": False,
                    "message": f"连接失败: {error_message}",
                    "error": error_data
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "连接超时，请检查网络或API地址"
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到API服务器，请检查API地址"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"测试失败: {str(e)}"
        } 