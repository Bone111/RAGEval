from fastapi import APIRouter, File, UploadFile, Body, Form
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

router = APIRouter()

@router.post("/mineru-upload-and-parse")
async def mineru_upload_and_parse(
    file: UploadFile = File(..., description="要上传并解析的文件"),
    token: str = Form(..., description="Mineru在线API的token"),
    is_ocr: bool = Form(True, description="是否启用OCR"),
    enable_formula: bool = Form(True, description="是否启用公式识别")
):
    import requests
    try:
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
            'Authorization': f'Bearer {token}'
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
        if resp.status_code != 200:
            return {"error": f"获取上传URL失败: {resp.text}"}
        result = resp.json()
        if result.get("code") != 0:
            return {"error": f"获取上传URL失败: {result.get('msg')}"}
        batch_id = result["data"]["batch_id"]
        file_url = result["data"]["file_urls"][0]
        print("文件上传成功，返回内容：", batch_id)  # 仅用于调试

        # Step 2: 上传文件
        file.file.seek(0)
        upload_resp = requests.put(file_url, data=file.file)
        print("返回内容：", status_result)  # 仅用于调试
        if upload_resp.status_code != 200:
            return {"error": f"文件上传失败: {upload_resp.text}"}
        

        # Step 3: 轮询查询任务状态，直到所有文件完成或失败
        status_url = f'https://mineru.net/api/v4/extract-results/batch/{batch_id}'
        poll_headers = {
            'Authorization': f'Bearer {token}'
        }
        final_files = None
        for _ in range(120):  # 最多轮询120次
            time.sleep(2)  # 每次间隔2秒
            status_resp = requests.get(status_url, headers=poll_headers)
            print('轮询返回原始文本:', status_resp.text)
            if status_resp.status_code != 200:
                return {
                    "error": f"查询任务状态接口返回非200: {status_resp.status_code}",
                    "raw": status_resp.text,
                    "url": status_url,
                    "headers": poll_headers
                }
            try:
                status_result = status_resp.json()
                print('轮询返回JSON:', status_result)
            except Exception as e:
                return {
                    "error": f"解析任务状态接口返回非JSON: {str(e)}",
                    "raw": status_resp.text,
                    "status_code": status_resp.status_code,
                    "url": status_url,
                    "headers": poll_headers
                }
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
            return {"error": "超时未获取到全部文件最终状态", "detail": status_result if status_result is not None else {}, "url": status_url, "headers": poll_headers}
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
    except Exception as e:
        return {"error": str(e)} 

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