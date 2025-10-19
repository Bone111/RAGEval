from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import tempfile
import os
from pathlib import Path
import logging
from app.services.file_parser_service import FileParserService
from app.api.deps import get_current_user
from app.models.user import User
from app.api.api_v1.endpoints.mineru_convert import mineru_upload_and_parse
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化文件解析服务
file_parser_service = FileParserService()

@router.post("/parse-file/")
async def parse_file(
    file: UploadFile = File(...),
    encoding: Optional[str] = "utf-8",
    use_mineru: Optional[bool] = False,
    mineru_token: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    解析上传的文件并转换为Markdown格式
    支持选择使用本地解析或mineru在线API解析
    """
    try:
        # 如果选择使用mineru
        if use_mineru:
            # 优先使用配置的密钥，如果没有则使用传入的token
            api_token = settings.MINERU_API_KEY or mineru_token
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
            
            # 使用mineru在线API解析
            result = await mineru_upload_and_parse(
                file=file,
                token=api_token,
                is_ocr=True,
                enable_formula=False
            )
            
            if "error" in result:
                # 如果MinerU返回的是结构化错误，直接传递
                if isinstance(result["error"], dict):
                    raise HTTPException(status_code=500, detail=result["error"])
                else:
                    # 如果是简单字符串错误，包装成结构化错误
                    raise HTTPException(
                        status_code=500, 
                        detail={
                            "error": "MinerU解析失败",
                            "message": result["error"],
                            "action": "retry"
                        }
                    )
            
            return {
                "success": True,
                "filename": file.filename,
                "file_size": len(await file.read()),
                "md_content": result.get("md_text", ""),
                "message": "文件解析成功（使用mineru在线API）",
                "parser_type": "mineru_online"
            }
        
        # 使用本地解析（原有逻辑）
        # 检查文件大小（限制为50MB）
        file_size = 0
        file_content = b""
        chunk_size = 1024 * 1024  # 1MB chunks
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_content += chunk
            file_size += len(chunk)
            
            if file_size > 50 * 1024 * 1024:  # 50MB
                raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
        
        # 检查文件格式
        if not file_parser_service.is_supported(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式: {Path(file.filename).suffix}"
            )
        
        # 解析文件
        md_content = file_parser_service.parse_file_bytes(
            file_content, 
            file.filename, 
            encoding=encoding
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "file_size": file_size,
            "md_content": md_content,
            "message": "文件解析成功（使用本地解析）",
            "parser_type": "local"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")

@router.post("/parse-file-info/")
async def get_file_info(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取文件信息（不解析内容）
    """
    try:
        # 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as temp_file:
            file_content = await file.read()
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        try:
            file_info = file_parser_service.get_file_info(temp_file_path)
            parser_info = file_parser_service.get_parser_info()
            
            return {
                "success": True,
                "file_info": file_info,
                "parser_info": parser_info,
                "message": "文件信息获取成功"
            }
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        logger.error(f"获取文件信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文件信息失败: {str(e)}")

@router.get("/supported-formats/")
async def get_supported_formats(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取支持的文件格式列表
    """
    try:
        parser_info = file_parser_service.get_parser_info()
        
        return {
            "success": True,
            "supported_formats": parser_info['supported_formats'],
            "libraries": parser_info['libraries'],
            "installation_guide": parser_info['installation_guide'],
            "message": "获取支持格式成功"
        }
        
    except Exception as e:
        logger.error(f"获取支持格式失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取支持格式失败: {str(e)}")

@router.get("/parser-status/")
async def get_parser_status(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取本地解析器状态
    """
    try:
        parser_status = file_parser_service.get_parser_status()
        
        return {
            "success": True,
            "parser_status": parser_status,
            "message": "获取解析器状态成功"
        }
        
    except Exception as e:
        logger.error(f"获取解析器状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取解析器状态失败: {str(e)}")

@router.post("/batch-parse/")
async def batch_parse_files(
    files: list[UploadFile] = File(...),
    encoding: Optional[str] = "utf-8",
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    批量解析多个文件
    """
    try:
        if len(files) > 10:
            raise HTTPException(status_code=400, detail="一次最多只能处理10个文件")
        
        results = []
        total_size = 0
        
        for file in files:
            try:
                # 检查文件大小
                file_content = await file.read()
                file_size = len(file_content)
                total_size += file_size
                
                if total_size > 100 * 1024 * 1024:  # 100MB总限制
                    raise HTTPException(status_code=413, detail="所有文件总大小超过100MB限制")
                
                # 检查文件格式
                if not file_parser_service.is_supported(file.filename):
                    results.append({
                        "filename": file.filename,
                        "success": False,
                        "error": f"不支持的文件格式: {Path(file.filename).suffix}"
                    })
                    continue
                
                # 解析文件
                md_content = file_parser_service.parse_file_bytes(
                    file_content, 
                    file.filename, 
                    encoding=encoding
                )
                
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "file_size": file_size,
                    "md_content": md_content
                })
                
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        success_count = sum(1 for r in results if r['success'])
        
        return {
            "success": True,
            "total_files": len(files),
            "success_count": success_count,
            "failed_count": len(files) - success_count,
            "results": results,
            "message": f"批量解析完成，成功 {success_count} 个文件"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量解析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"批量解析失败: {str(e)}")

@router.post("/parse-with-options/")
async def parse_file_with_options(
    file: UploadFile = File(...),
    encoding: Optional[str] = "utf-8",
    include_tables: Optional[bool] = True,
    include_images: Optional[bool] = True,
    ocr_language: Optional[str] = "chi_sim+eng",
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    使用自定义选项解析文件
    """
    try:
        # 读取文件内容
        file_content = await file.read()
        file_size = len(file_content)
        
        if file_size > 50 * 1024 * 1024:  # 50MB
            raise HTTPException(status_code=413, detail="文件大小超过50MB限制")
        
        # 检查文件格式
        if not file_parser_service.is_supported(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件格式: {Path(file.filename).suffix}"
            )
        
        # 构建解析选项
        parse_options = {
            'encoding': encoding,
            'include_tables': include_tables,
            'include_images': include_images,
            'ocr_language': ocr_language
        }
        
        # 解析文件
        md_content = file_parser_service.parse_file_bytes(
            file_content, 
            file.filename, 
            **parse_options
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "file_size": file_size,
            "parse_options": parse_options,
            "md_content": md_content,
            "message": "文件解析成功"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件解析失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}") 