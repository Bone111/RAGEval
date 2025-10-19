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

class LLMEvaluationRequest(BaseModel):
    base_url: str
    api_key: str
    model_name: str
    user_message: str
    system_message: str = "你是一个专业的RAG回答评估专家，你的任务是评估生成式AI的回答质量。请根据提供的标准答案评价RAG系统的回答质量，分析其准确性、相关性和完整性。"
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

@router.post("/llm/evaluate")
async def llm_evaluation(request: LLMEvaluationRequest):
    """精度评测LLM请求代理"""
    try:
        headers = {
            "Content-Type": "application/json"
        }
        if request.api_key:
            headers["Authorization"] = f"Bearer {request.api_key}"

        # 构建评测消息
        payload = {
            "model": request.model_name,
            "messages": [
                {"role": "system", "content": request.system_message},
                {"role": "user", "content": request.user_message}
            ],
            "temperature": 0.2,
            "max_tokens": 1000
        }
        
        # 合并额外参数
        if request.additional_params:
            payload.update(request.additional_params)

        async with httpx.AsyncClient(timeout=120.0) as client:
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
                    "content": content,
                    "raw_response": result
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                return {
                    "success": False,
                    "message": f"评测请求失败: {error_message}",
                    "error": error_data
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "评测请求超时，请检查网络或API地址"
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到API服务器，请检查API地址"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"评测请求失败: {str(e)}"
        }

class RAGFlowTestRequest(BaseModel):
    address: str
    chat_id: str
    api_key: str
    test_message: str = "测试问题"

@router.post("/ragflow/test")
async def test_ragflow_connection(request: RAGFlowTestRequest):
    """测试RAGFlow连接是否正常"""
    try:
        # 构建RAGFlow API URL
        base_url = f"http://{request.address}/api/v1/chats_openai/{request.chat_id}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {request.api_key}"
        }

        # 构建测试消息
        payload = {
            "model": "model",
            "messages": [
                {"role": "user", "content": request.test_message}
            ],
            "stream": False
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {
                    "success": True,
                    "message": "RAGFlow连接成功",
                    "response": content[:100] + "..." if len(content) > 100 else content
                }
            else:
                error_data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                error_message = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                return {
                    "success": False,
                    "message": f"RAGFlow连接失败: {error_message}",
                    "error": error_data
                }
                
    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "RAGFlow连接超时，请检查网络或地址"
        }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": "无法连接到RAGFlow服务器，请检查地址"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"RAGFlow测试失败: {str(e)}"
        } 