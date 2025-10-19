import os
import tempfile
import mimetypes
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging
from io import BytesIO

# PDF处理
try:
    import PyPDF2
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# Word文档处理
try:
    import docx
    from docx import Document
    WORD_AVAILABLE = True
except ImportError:
    WORD_AVAILABLE = False

# Excel处理
try:
    import pandas as pd
    import openpyxl
    from openpyxl import load_workbook
    EXCEL_AVAILABLE = True
except ImportError:
    EXCEL_AVAILABLE = False

# PowerPoint处理
try:
    from pptx import Presentation
    PPT_AVAILABLE = True
except ImportError:
    PPT_AVAILABLE = False

# 图片OCR处理
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# 文本处理
import re
import json

logger = logging.getLogger(__name__)

class FileParserService:
    """文件解析服务，支持多种文件格式转换为Markdown"""
    
    def __init__(self):
        self.supported_formats = {
            '.pdf': 'PDF文档',
            '.doc': 'Word文档',
            '.docx': 'Word文档',
            '.xls': 'Excel表格',
            '.xlsx': 'Excel表格',
            '.ppt': 'PowerPoint演示文稿',
            '.pptx': 'PowerPoint演示文稿',
            '.txt': '文本文件',
            '.md': 'Markdown文件',
            '.html': 'HTML文件',
            '.htm': 'HTML文件',
            '.jpg': '图片文件',
            '.jpeg': '图片文件',
            '.png': '图片文件',
            '.bmp': '图片文件',
            '.tiff': '图片文件',
            '.tif': '图片文件'
        }
    
    def is_supported(self, file_path: str) -> bool:
        """检查文件格式是否支持"""
        file_ext = Path(file_path).suffix.lower()
        return file_ext in self.supported_formats
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """获取文件信息"""
        file_path = Path(file_path)
        mime_type, _ = mimetypes.guess_type(str(file_path))
        
        return {
            'name': file_path.name,
            'extension': file_path.suffix.lower(),
            'mime_type': mime_type,
            'size': file_path.stat().st_size if file_path.exists() else 0,
            'supported': self.is_supported(str(file_path))
        }
    
    def parse_file(self, file_path: str, **kwargs) -> str:
        """解析文件并转换为Markdown格式"""
        file_ext = Path(file_path).suffix.lower()
        
        if not self.is_supported(file_path):
            raise ValueError(f"不支持的文件格式: {file_ext}")
        
        try:
            if file_ext == '.pdf':
                return self._parse_pdf(file_path, **kwargs)
            elif file_ext in ['.doc', '.docx']:
                return self._parse_word(file_path, **kwargs)
            elif file_ext in ['.xls', '.xlsx']:
                return self._parse_excel(file_path, **kwargs)
            elif file_ext in ['.ppt', '.pptx']:
                return self._parse_powerpoint(file_path, **kwargs)
            elif file_ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
                return self._parse_image(file_path, **kwargs)
            elif file_ext in ['.txt', '.md']:
                return self._parse_text(file_path, **kwargs)
            elif file_ext in ['.html', '.htm']:
                return self._parse_html(file_path, **kwargs)
            else:
                raise ValueError(f"未实现的文件格式解析: {file_ext}")
        except Exception as e:
            logger.error(f"解析文件 {file_path} 失败: {str(e)}")
            raise
    
    def _parse_pdf(self, file_path: str, **kwargs) -> str:
        """解析PDF文件"""
        if not PDF_AVAILABLE:
            raise ImportError("PDF解析库未安装。请运行以下命令安装：\npip install PyPDF2 pdfplumber\n\n或者使用MinerU在线解析功能。")
        
        md_content = []
        md_content.append(f"# {Path(file_path).stem}\n")
        
        try:
            # 使用pdfplumber提取文本和表格
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                md_content.append(f"**文档信息**: PDF文档，共 {total_pages} 页\n\n")
                
                for page_num, page in enumerate(pdf.pages, 1):
                    md_content.append(f"## 第 {page_num} 页\n")
                    
                    # 提取文本
                    text = page.extract_text()
                    if text:
                        md_content.append("### 文本内容\n")
                        md_content.append(text.strip())
                        md_content.append("\n")
                    
                    # 提取表格
                    tables = page.extract_tables()
                    if tables:
                        md_content.append("### 表格内容\n")
                        for table_num, table in enumerate(tables, 1):
                            if table:
                                md_content.append(f"#### 表格 {table_num}\n")
                                md_content.append(self._table_to_markdown(table))
                                md_content.append("\n")
                    
                    md_content.append("---\n")
        
        except Exception as e:
            logger.warning(f"pdfplumber解析失败，尝试使用PyPDF2: {str(e)}")
            # 降级到PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                md_content.append(f"**文档信息**: PDF文档，共 {total_pages} 页\n\n")
                
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    md_content.append(f"## 第 {page_num} 页\n")
                    text = page.extract_text()
                    if text:
                        md_content.append(text.strip())
                        md_content.append("\n")
                    md_content.append("---\n")
        
        return "\n".join(md_content)
    
    def _parse_word(self, file_path: str, **kwargs) -> str:
        """解析Word文档"""
        if not WORD_AVAILABLE:
            raise ImportError("Word解析库未安装。请运行以下命令安装：\npip install python-docx\n\n或者使用MinerU在线解析功能。")
        
        md_content = []
        doc = Document(file_path)
        
        # 文档标题
        if doc.core_properties.title:
            md_content.append(f"# {doc.core_properties.title}\n")
        else:
            md_content.append(f"# {Path(file_path).stem}\n")
        
        # 文档信息
        info = []
        if doc.core_properties.author:
            info.append(f"作者: {doc.core_properties.author}")
        if doc.core_properties.created:
            info.append(f"创建时间: {doc.core_properties.created}")
        if doc.core_properties.modified:
            info.append(f"修改时间: {doc.core_properties.modified}")
        
        if info:
            md_content.append("**文档信息**: " + " | ".join(info) + "\n\n")
        
        # 解析段落
        for para in doc.paragraphs:
            if para.text.strip():
                # 检查段落样式
                if para.style.name.startswith('Heading'):
                    level = para.style.name[-1]
                    if level.isdigit():
                        heading_level = int(level)
                        md_content.append(f"{'#' * heading_level} {para.text}\n")
                    else:
                        md_content.append(f"## {para.text}\n")
                else:
                    md_content.append(f"{para.text}\n\n")
        
        # 解析表格
        for table in doc.tables:
            md_content.append("### 表格\n")
            table_data = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            
            if table_data:
                md_content.append(self._table_to_markdown(table_data))
                md_content.append("\n")
        
        return "\n".join(md_content)
    
    def _parse_excel(self, file_path: str, **kwargs) -> str:
        """解析Excel文件"""
        if not EXCEL_AVAILABLE:
            raise ImportError("Excel解析库未安装。请运行以下命令安装：\npip install pandas openpyxl\n\n或者使用MinerU在线解析功能。")
        
        md_content = []
        md_content.append(f"# {Path(file_path).stem}\n")
        
        try:
            # 使用pandas读取所有工作表
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            
            md_content.append(f"**文档信息**: Excel文档，共 {len(sheet_names)} 个工作表\n\n")
            
            for sheet_name in sheet_names:
                md_content.append(f"## 工作表: {sheet_name}\n")
                
                # 读取工作表数据
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                if not df.empty:
                    # 转换为表格格式
                    table_data = [df.columns.tolist()] + df.values.tolist()
                    md_content.append(self._table_to_markdown(table_data))
                    md_content.append("\n")
                    
                    # 添加数据统计信息
                    md_content.append("### 数据统计\n")
                    md_content.append(f"- 行数: {len(df)}\n")
                    md_content.append(f"- 列数: {len(df.columns)}\n")
                    md_content.append(f"- 列名: {', '.join(df.columns.tolist())}\n\n")
                else:
                    md_content.append("*空工作表*\n\n")
                
                md_content.append("---\n")
        
        except Exception as e:
            logger.error(f"Excel解析失败: {str(e)}")
            raise
        
        return "\n".join(md_content)
    
    def _parse_powerpoint(self, file_path: str, **kwargs) -> str:
        """解析PowerPoint文件"""
        if not PPT_AVAILABLE:
            raise ImportError("PowerPoint解析库未安装。请运行以下命令安装：\npip install python-pptx\n\n或者使用MinerU在线解析功能。")
        
        md_content = []
        prs = Presentation(file_path)
        
        # 文档标题
        md_content.append(f"# {Path(file_path).stem}\n")
        md_content.append(f"**文档信息**: PowerPoint演示文稿，共 {len(prs.slides)} 张幻灯片\n\n")
        
        for slide_num, slide in enumerate(prs.slides, 1):
            md_content.append(f"## 幻灯片 {slide_num}\n")
            
            # 提取幻灯片标题
            title = ""
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    if not title:
                        title = shape.text.strip()
                        md_content.append(f"### {title}\n")
                    else:
                        md_content.append(f"{shape.text.strip()}\n")
            
            if not title:
                md_content.append(f"### 幻灯片 {slide_num}\n")
            
            md_content.append("\n---\n")
        
        return "\n".join(md_content)
    
    def _parse_image(self, file_path: str, **kwargs) -> str:
        """解析图片文件（OCR）"""
        if not OCR_AVAILABLE:
            raise ImportError("OCR库未安装。请运行以下命令安装：\npip install pytesseract opencv-python\n\n注意：还需要安装Tesseract OCR引擎。\n或者使用MinerU在线解析功能。")
        
        md_content = []
        md_content.append(f"# {Path(file_path).stem}\n")
        md_content.append("**文档信息**: 图片文件\n\n")
        
        try:
            # 读取图片
            image = cv2.imread(file_path)
            if image is None:
                raise ValueError("无法读取图片文件")
            
            # 转换为PIL Image
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(image_rgb)
            
            # OCR识别
            md_content.append("## 图片内容识别\n")
            
            # 尝试不同的OCR配置
            ocr_configs = [
                '--oem 3 --psm 6',  # 默认配置
                '--oem 3 --psm 3',  # 自动页面分割
                '--oem 3 --psm 1',  # 自动页面分割，带OSD
            ]
            
            text_extracted = False
            for config in ocr_configs:
                try:
                    text = pytesseract.image_to_string(pil_image, config=config, lang='chi_sim+eng')
                    if text.strip():
                        md_content.append(text.strip())
                        text_extracted = True
                        break
                except Exception as e:
                    logger.warning(f"OCR配置 {config} 失败: {str(e)}")
                    continue
            
            if not text_extracted:
                md_content.append("*无法识别图片中的文字内容*\n")
            
            # 尝试识别表格
            try:
                tables = pytesseract.image_to_data(pil_image, output_type=pytesseract.Output.DATAFRAME)
                if not tables.empty:
                    md_content.append("\n## 表格识别\n")
                    # 这里可以进一步处理表格数据
                    md_content.append("*检测到表格结构，但需要进一步处理*\n")
            except Exception as e:
                logger.warning(f"表格识别失败: {str(e)}")
        
        except Exception as e:
            logger.error(f"图片OCR失败: {str(e)}")
            md_content.append(f"*图片处理失败: {str(e)}*\n")
        
        return "\n".join(md_content)
    
    def _parse_text(self, file_path: str, **kwargs) -> str:
        """解析文本文件"""
        encoding = kwargs.get('encoding', 'utf-8')
        
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            
            # 如果是Markdown文件，直接返回
            if Path(file_path).suffix.lower() == '.md':
                return content
            
            # 普通文本文件，添加标题
            md_content = []
            md_content.append(f"# {Path(file_path).stem}\n")
            md_content.append("**文档信息**: 文本文件\n\n")
            md_content.append(content)
            
            return "\n".join(md_content)
        
        except UnicodeDecodeError:
            # 尝试其他编码
            for encoding in ['gbk', 'gb2312', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        content = file.read()
                    
                    md_content = []
                    md_content.append(f"# {Path(file_path).stem}\n")
                    md_content.append(f"**文档信息**: 文本文件 (编码: {encoding})\n\n")
                    md_content.append(content)
                    
                    return "\n".join(md_content)
                except UnicodeDecodeError:
                    continue
            
            raise ValueError("无法识别文件编码")
    
    def _parse_html(self, file_path: str, **kwargs) -> str:
        """解析HTML文件"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("HTML解析库未安装。请运行以下命令安装：\npip install beautifulsoup4\n\n或者使用MinerU在线解析功能。")
        
        encoding = kwargs.get('encoding', 'utf-8')
        
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                html_content = file.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            md_content = []
            
            # 提取标题
            title = soup.find('title')
            if title:
                md_content.append(f"# {title.get_text().strip()}\n")
            else:
                md_content.append(f"# {Path(file_path).stem}\n")
            
            md_content.append("**文档信息**: HTML文件\n\n")
            
            # 提取正文内容
            body = soup.find('body')
            if body:
                # 移除script和style标签
                for script in body(["script", "style"]):
                    script.decompose()
                
                # 提取文本
                text = body.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)
                
                md_content.append(text)
            else:
                md_content.append("*无正文内容*")
            
            return "\n".join(md_content)
        
        except Exception as e:
            logger.error(f"HTML解析失败: {str(e)}")
            raise
    
    def _table_to_markdown(self, table_data: List[List[str]]) -> str:
        """将表格数据转换为Markdown表格格式"""
        if not table_data:
            return ""
        
        md_lines = []
        
        # 添加表头
        header = table_data[0]
        md_lines.append("| " + " | ".join(str(cell) for cell in header) + " |")
        
        # 添加分隔线
        md_lines.append("| " + " | ".join("---" for _ in header) + " |")
        
        # 添加数据行
        for row in table_data[1:]:
            md_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(md_lines)
    
    def parse_file_bytes(self, file_bytes: bytes, filename: str, **kwargs) -> str:
        """从字节数据解析文件"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as temp_file:
            temp_file.write(file_bytes)
            temp_file_path = temp_file.name
        
        try:
            return self.parse_file(temp_file_path, **kwargs)
        finally:
            # 清理临时文件
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
    
    def get_parser_info(self) -> Dict[str, Any]:
        """获取解析器信息"""
        return {
            'supported_formats': self.supported_formats,
            'libraries': {
                'pdf': PDF_AVAILABLE,
                'word': WORD_AVAILABLE,
                'excel': EXCEL_AVAILABLE,
                'powerpoint': PPT_AVAILABLE,
                'ocr': OCR_AVAILABLE
            },
            'installation_guide': {
                'pdf': 'pip install PyPDF2 pdfplumber',
                'word': 'pip install python-docx',
                'excel': 'pip install pandas openpyxl',
                'powerpoint': 'pip install python-pptx',
                'ocr': 'pip install pytesseract opencv-python\n注意：还需要安装Tesseract OCR引擎',
                'html': 'pip install beautifulsoup4'
            }
        }
    
    def get_parser_status(self) -> Dict[str, Any]:
        """获取解析器状态"""
        available_formats = []
        missing_formats = []
        
        for ext, desc in self.supported_formats.items():
            if ext == '.pdf' and PDF_AVAILABLE:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.doc', '.docx'] and WORD_AVAILABLE:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.xls', '.xlsx'] and EXCEL_AVAILABLE:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.ppt', '.pptx'] and PPT_AVAILABLE:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'] and OCR_AVAILABLE:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.txt', '.md']:
                available_formats.append(f"{ext} ({desc})")
            elif ext in ['.html', '.htm']:
                try:
                    from bs4 import BeautifulSoup
                    available_formats.append(f"{ext} ({desc})")
                except ImportError:
                    missing_formats.append(f"{ext} ({desc})")
            else:
                missing_formats.append(f"{ext} ({desc})")
        
        return {
            'available_formats': available_formats,
            'missing_formats': missing_formats,
            'total_formats': len(self.supported_formats),
            'available_count': len(available_formats),
            'missing_count': len(missing_formats),
            'is_fully_configured': len(missing_formats) == 0
        } 