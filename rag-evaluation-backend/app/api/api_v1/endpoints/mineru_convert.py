from fastapi import APIRouter, File, UploadFile, Body, Form, HTTPException, Depends
import tempfile
import os
import asyncio
import threading
import uuid
import time
from pathlib import Path
import requests
import zipfile
import io
import shutil
from app.core.config import settings
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_config import UserMinerUConfig
from sqlalchemy.orm import Session

router = APIRouter()

@router.post("/mineru-upload-and-parse")
async def mineru_upload_and_parse(
    file: UploadFile = File(..., description="要上传并解析的文件"),
    token: str = Form(None, description="Mineru在线API的token（可选，优先使用配置的密钥）"),
    is_ocr: bool = Form(True, description="是否启用OCR"),
    enable_formula: bool = Form(True, description="是否启用公式识别"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import requests
    try:
        # 优先使用用户配置的密钥，其次使用环境变量，最后使用传入的token
        user_config = db.query(UserMinerUConfig).filter(
            UserMinerUConfig.user_id == current_user.id,
            UserMinerUConfig.is_active == True
        ).first()
        
        api_token = None
        if user_config:
            api_token = user_config.api_key
        elif token:
            api_token = token
            
        if not api_token:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "MinerU API密钥未配置",
                    "message": "请先在系统设置中配置MinerU API密钥，或联系管理员设置环境变量",
                    "action": "configure_mineru",
                    "redirect_to": "/settings?tab=mineru"
                }
            )
        
        status_result = None  # 一定要在try块最前面初始化，彻底解决作用域问题
        STATIC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../static'))
        # 获取不带扩展名的文件名作为目录名
        filename_no_ext = os.path.splitext(file.filename)[0]
        file_dir = os.path.join(STATIC_ROOT, "mineru_cache", filename_no_ext)
        if os.path.exists(file_dir) and any(os.path.isfile(os.path.join(root, f)) for root, _, files in os.walk(file_dir) for f in files):
            print(f"[mineru] 命中本地缓存: {file_dir}，文件: {file.filename}")
            extracted_files = []
            md_text = None
            for root, _, files in os.walk(file_dir):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), STATIC_ROOT)
                    rel_path = rel_path.replace("\\", "/")
                    static_rel_path = f"/static/{rel_path}"
                    extracted_files.append(static_rel_path)
                    if f.endswith('.md'):
                        try:
                            with open(os.path.join(root, f), 'r', encoding='utf-8') as md_file:
                                md_text = md_file.read()
                        except Exception as e:
                            pass
            return {
                "status": "success",
                "files": [{
                    "filename": file.filename,
                    "state": "done",
                    "error_msg": None,
                    "full_zip_url": None,
                    "success": True,
                    "md_text": md_text,
                    "extracted_files": extracted_files
                }]
            }
        # Step 1: 获取上传URL
        url = 'https://mineru.net/api/v4/file-urls/batch'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_token}'
        }
        data = {
            "enable_formula": enable_formula,
            "language": "auto",  # 可根据需要调整
            "enable_table": True,
            "model_version":'v2',
            "files": [
                {"name": file.filename, "is_ocr": is_ocr, "data_id": "file1"}
            ]
        }
        resp = requests.post(url, headers=headers, json=data)
        if resp.status_code == 401:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "MinerU API密钥无效或已过期",
                    "message": "请检查API密钥是否正确，或联系管理员更新密钥",
                    "action": "check_key",
                    "redirect_to": "/settings?tab=mineru"
                }
            )
        elif resp.status_code != 200:
            raise HTTPException(
                status_code=resp.status_code,
                detail={
                    "error": "MinerU API请求失败",
                    "message": f"获取上传URL失败: {resp.text}",
                    "action": "retry",
                    "status_code": resp.status_code
                }
            )
        result = resp.json()
        if result.get("code") != 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "MinerU API返回错误",
                    "message": f"获取上传URL失败: {result.get('msg')}",
                    "action": "retry",
                    "api_code": result.get("code")
                }
            )
        batch_id = result["data"]["batch_id"]
        file_url = result["data"]["file_urls"][0]
        print("文件上传成功，返回内容：", batch_id)  # 仅用于调试

        # Step 2: 上传文件
        file.file.seek(0)
        upload_resp = requests.put(file_url, data=file.file)
        print("返回内容：", status_result)  # 仅用于调试
        if upload_resp.status_code != 200:
            raise HTTPException(
                status_code=upload_resp.status_code,
                detail={
                    "error": "文件上传失败",
                    "message": f"文件上传失败: {upload_resp.text}",
                    "action": "retry"
                }
            )
        

        # Step 3: 轮询查询任务状态，直到所有文件完成或失败
        status_url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
        poll_headers = {
            'Authorization': f'Bearer {api_token}'
        }
        final_files = None
        for _ in range(120):  # 最多轮询120次
            time.sleep(2)  # 每次间隔2秒
            status_resp = requests.get(status_url, headers=poll_headers)
            print('轮询返回原始文本:', status_resp.text)
            if status_resp.status_code == 401:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "MinerU API密钥无效或已过期",
                        "message": "查询任务状态时发现API密钥无效，请检查密钥配置",
                        "action": "check_key",
                        "redirect_to": "/settings?tab=mineru"
                    }
                )
            elif status_resp.status_code != 200:
                raise HTTPException(
                    status_code=status_resp.status_code,
                    detail={
                        "error": "查询任务状态失败",
                        "message": f"查询任务状态接口返回非200: {status_resp.status_code}",
                        "action": "retry",
                        "status_code": status_resp.status_code
                    }
                )
            try:
                status_result = status_resp.json()
                print('轮询返回JSON:', status_result)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "解析任务状态失败",
                        "message": f"解析任务状态接口返回非JSON: {str(e)}",
                        "action": "retry"
                    }
                )
            if isinstance(status_result, dict):
                data = status_result.get("data", {})
                data_list = data.get("extract_result", [])
            else:
                data_list = []
            files_status = []
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                file_status = {
                    "filename": item.get("file_name"),
                    "state": item.get("state"),
                    "error_msg": item.get("err_msg"),
                    "full_zip_url": item.get("full_zip_url"),
                }
                file_status["success"] = item.get("state") == "done" and bool(item.get("full_zip_url"))
                files_status.append(file_status)
            # 新逻辑：只要有一个文件 success==True 就立即返回
            if any(f.get("success") for f in files_status):
                final_files = files_status
                break
        else:
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "文件解析超时",
                    "message": "文件解析超时，请稍后重试或联系管理员",
                    "action": "retry"
                }
            )
        if final_files is None:
            final_files = []

        # Step 4: 对于已完成的文件，仅用full_zip_url下载zip并提取md内容
        for file_status in final_files:
            if not isinstance(file_status, dict):
                continue
            file_status["md_text"] = None
            file_status["extracted_files"] = []
            # 只处理 success==True 的文件
            if file_status.get("success"):
                batch_id_safe = str(batch_id).replace('/', '_')
                # 用不带扩展名的文件名作为目录名
                filename_no_ext = os.path.splitext(file_status['filename'])[0]
                file_dir = os.path.join(STATIC_ROOT, "mineru_cache", filename_no_ext)
                # 如果本地已存在同名解析目录且有文件，直接用本地文件
                if os.path.exists(file_dir) and any(os.path.isfile(os.path.join(root, f)) for root, _, files in os.walk(file_dir) for f in files):
                    print(f"[mineru] 命中本地缓存: {file_dir}，文件: {file_status['filename']}")
                    for root, _, files in os.walk(file_dir):
                        for f in files:
                            rel_path = os.path.relpath(os.path.join(root, f), STATIC_ROOT)
                            rel_path = rel_path.replace("\\", "/")
                            static_rel_path = f"/static/{rel_path}"
                            file_status["extracted_files"].append(static_rel_path)
                            # 如果是md文件，读取内容
                            if f.endswith('.md'):
                                try:
                                    with open(os.path.join(root, f), 'r', encoding='utf-8') as md_file:
                                        file_status["md_text"] = md_file.read()
                                except Exception as e:
                                    file_status["error_msg"] = f"读取md文件失败: {str(e)}"
                    continue  # 跳过下载和解压
                zip_resp = requests.get(file_status["full_zip_url"])
                if zip_resp.status_code == 200:
                    try:
                        # 解压到 static/mineru_cache/{filename_no_ext}/
                        if os.path.exists(file_dir):
                            shutil.rmtree(file_dir)
                        os.makedirs(file_dir, exist_ok=True)
                        with zipfile.ZipFile(io.BytesIO(zip_resp.content)) as zf:
                            for name in zf.namelist():
                                out_path = os.path.join(file_dir, name)
                                # 创建子目录
                                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                                with zf.open(name) as src, open(out_path, 'wb') as dst:
                                    dst.write(src.read())
                                # 记录静态路径
                                static_rel_path = f"/static/mineru_cache/{filename_no_ext}/{name}"
                                file_status["extracted_files"].append(static_rel_path)
                                # 如果是md文件，额外读取内容
                                if name.endswith('.md'):
                                    try:
                                        with open(out_path, 'r', encoding='utf-8') as md_file:
                                            file_status["md_text"] = md_file.read()
                                    except Exception as e:
                                        file_status["error_msg"] = f"读取md文件失败: {str(e)}"
                    except Exception as e:
                        file_status["error_msg"] = f"解压zip失败: {str(e)}"
                else:
                    file_status["error_msg"] = f"下载zip失败: {zip_resp.text}"
        print("final_files 返回内容:")
        import pprint; pprint.pprint(final_files)
        return {
            "status": "success",
            "files": final_files
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "文件解析失败",
                "message": f"文件解析过程中发生未知错误: {str(e)}",
                "action": "retry"
            }
        ) 

@router.get("/mineru-config-status")
async def get_mineru_config_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    检查MinerU配置状态
    """
    try:
        # 检查用户配置和环境变量配置
        user_config = db.query(UserMinerUConfig).filter(
            UserMinerUConfig.user_id == current_user.id,
            UserMinerUConfig.is_active == True
        ).first()
        
        has_user_config = bool(user_config)
        has_config = has_user_config
        
        # 尝试测试API连接
        api_status = "unknown"
        error_message = None
        
        # 使用用户配置的密钥进行测试
        test_key = None
        config_source = "none"
        if user_config:
            # 检查密钥是否为空
            if user_config.api_key and user_config.api_key.strip():
                test_key = user_config.api_key
                config_source = "user"
            else:
                # 密钥为空，视为未配置
                api_status = "error"
                error_message = "MinerU API密钥为空，请重新配置"
        else:
            # 没有配置时，设置状态为error而不是unknown
            api_status = "error"
            error_message = "未配置MinerU API密钥"
            
        if test_key:
            try:
                # 简单的API测试请求 - 使用更宽松的验证
                test_url = 'https://mineru.net/api/v4/file-urls/batch'
                test_headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {test_key}'
                }
                test_data = {
                    "enable_formula": False,
                    "language": "auto",
                    "enable_table": True,
                    "model_version": 'v2',
                    "files": []
                }
                
                print(f"测试MinerU API密钥: {test_key[:10]}...")
                response = requests.post(test_url, headers=test_headers, json=test_data, timeout=10)
                print(f"MinerU API响应状态: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        print(f"MinerU API响应内容: {result}")
                        # 更宽松的验证逻辑
                        if isinstance(result, dict):
                            if result.get("code") == 0:
                                api_status = "valid"
                                error_message = None
                            elif result.get("code") == -10002:
                                # -10002 表示文件列表为空，但密钥是有效的
                                api_status = "valid"
                                error_message = None
                            elif "code" in result:
                                api_status = "invalid"
                                error_message = result.get("msg", "API密钥无效")
                            else:
                                # 如果没有code字段，但有数据返回，认为有效
                                api_status = "valid"
                                error_message = None
                        else:
                            # 非JSON响应，但状态码200，认为有效
                            api_status = "valid"
                            error_message = None
                    except Exception as json_error:
                        print(f"JSON解析错误: {json_error}")
                        # JSON解析失败但状态码200，认为有效
                        api_status = "valid"
                        error_message = None
                elif response.status_code == 401:
                    api_status = "invalid"
                    error_message = "API密钥无效或已过期"
                elif response.status_code == 403:
                    api_status = "invalid"
                    error_message = "API密钥权限不足"
                else:
                    api_status = "error"
                    error_message = f"API请求失败: {response.status_code}"
                    print(f"MinerU API错误响应: {response.text}")
                    
            except requests.exceptions.Timeout:
                api_status = "timeout"
                error_message = "API请求超时"
            except requests.exceptions.RequestException as e:
                api_status = "error"
                error_message = f"网络错误: {str(e)}"
                print(f"MinerU API网络错误: {e}")
            except Exception as e:
                api_status = "error"
                error_message = f"未知错误: {str(e)}"
                print(f"MinerU API未知错误: {e}")
        
        return {
            "has_config": has_config,
            "api_status": api_status,
            "error_message": error_message,
            "config_source": config_source
        }
        
    except Exception as e:
        return {
            "has_config": False,
            "api_status": "error",
            "error_message": f"检查配置失败: {str(e)}",
            "config_source": "none"
        }

@router.post("/validate-api-key")
async def validate_mineru_api_key(
    request: dict,
    current_user: User = Depends(get_current_user)
):
    """
    验证MinerU API密钥有效性
    """
    api_key = request.get('api_key', '').strip()
    
    if not api_key:
        return {
            "is_valid": False,
            "error": "API密钥不能为空"
        }
    
    try:
        # 使用配额查询接口验证密钥
        quota_url = 'https://mineru.net/api/v4/quota'
        headers = {
            'Authorization': f'Bearer {api_key}'
        }
        
        response = requests.get(quota_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            try:
                result = response.json()
                if result.get("code") == 0:
                    # 密钥有效，返回配额信息
                    quota_data = result.get("data", {})
                    return {
                        "is_valid": True,
                        "quota": {
                            "user_left_quota": quota_data.get("user_left_quota", 0),
                            "total_left_quota": quota_data.get("total_left_quota", 0)
                        }
                    }
                else:
                    # 根据错误码判断具体问题
                    error_msg = result.get("msg", "密钥验证失败")
                    error_code = result.get("code")
                    
                    if error_code == -10002:  # Token过期
                        return {
                            "is_valid": False,
                            "error": "API密钥已过期"
                        }
                    elif error_code == -10001:  # Token错误
                        return {
                            "is_valid": False,
                            "error": "API密钥无效"
                        }
                    else:
                        return {
                            "is_valid": False,
                            "error": f"密钥验证失败: {error_msg}"
                        }
            except Exception as json_error:
                return {
                    "is_valid": False,
                    "error": "解析响应失败"
                }
        elif response.status_code == 401:
            return {
                "is_valid": False,
                "error": "API密钥无效或已过期"
            }
        else:
            return {
                "is_valid": False,
                "error": f"验证请求失败: {response.status_code}"
            }
            
    except requests.exceptions.Timeout:
        return {
            "is_valid": False,
            "error": "验证请求超时，请检查网络连接"
        }
    except requests.exceptions.RequestException as e:
        return {
            "is_valid": False,
            "error": f"网络错误: {str(e)}"
        }
    except Exception as e:
        return {
            "is_valid": False,
            "error": f"验证失败: {str(e)}"
        }

@router.post("/clear-mineru-cache")
def clear_mineru_cache():
    import shutil
    import os
    try:
        STATIC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../static'))
        mineru_cache_dir = os.path.join(STATIC_ROOT, "mineru_cache")
        if os.path.exists(mineru_cache_dir):
            shutil.rmtree(mineru_cache_dir)
            os.makedirs(mineru_cache_dir, exist_ok=True)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)} 