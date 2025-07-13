# 文件解析服务 (File Parser Service)

## 概述

文件解析服务是一个强大的工具，支持将多种格式的文件转换为Markdown格式。该服务集成了多种Python库来处理不同类型的文件，包括PDF、Word、Excel、PowerPoint、图片等。

## 支持的文件格式

### 文档格式
- **PDF** (.pdf) - 使用 pdfplumber 和 PyPDF2
- **Word** (.doc, .docx) - 使用 python-docx
- **Excel** (.xls, .xlsx) - 使用 pandas 和 openpyxl
- **PowerPoint** (.ppt, .pptx) - 使用 python-pptx

### 文本格式
- **纯文本** (.txt) - 支持多种编码
- **Markdown** (.md) - 直接读取
- **HTML** (.html, .htm) - 使用 BeautifulSoup 解析

### 图片格式
- **JPEG** (.jpg, .jpeg)
- **PNG** (.png)
- **BMP** (.bmp)
- **TIFF** (.tiff, .tif)

## 功能特性

### 1. 智能解析
- 自动识别文件类型
- 根据文件类型选择合适的解析策略
- 支持多种编码格式（UTF-8、GBK、GB2312等）

### 2. 表格处理
- 自动识别和提取表格结构
- 将表格转换为Markdown表格格式
- 保持表格的原始布局

### 3. 图片OCR
- 支持图片文字识别
- 多语言支持（中文、英文）
- 可配置OCR参数

### 4. 批量处理
- 支持批量上传和解析
- 进度跟踪和状态管理
- 错误处理和重试机制

## API 端点

### 1. 解析单个文件
```
POST /api/v1/file-parser/parse-file/
```

**参数：**
- `file`: 上传的文件
- `encoding`: 文件编码（可选，默认utf-8）

**响应：**
```json
{
  "success": true,
  "filename": "document.pdf",
  "file_size": 1024000,
  "md_content": "# 文档标题\n\n文档内容...",
  "message": "文件解析成功"
}
```

### 2. 获取文件信息
```
POST /api/v1/file-parser/parse-file-info/
```

**参数：**
- `file`: 上传的文件

**响应：**
```json
{
  "success": true,
  "file_info": {
    "name": "document.pdf",
    "extension": ".pdf",
    "mime_type": "application/pdf",
    "size": 1024000,
    "supported": true
  },
  "parser_info": {
    "supported_formats": {...},
    "libraries": {...}
  },
  "message": "文件信息获取成功"
}
```

### 3. 获取支持格式
```
GET /api/v1/file-parser/supported-formats/
```

**响应：**
```json
{
  "success": true,
  "supported_formats": {
    ".pdf": "PDF文档",
    ".doc": "Word文档",
    ".docx": "Word文档",
    ".xls": "Excel表格",
    ".xlsx": "Excel表格",
    ".ppt": "PowerPoint演示文稿",
    ".pptx": "PowerPoint演示文稿",
    ".txt": "文本文件",
    ".md": "Markdown文件",
    ".html": "HTML文件",
    ".htm": "HTML文件",
    ".jpg": "图片文件",
    ".jpeg": "图片文件",
    ".png": "图片文件",
    ".bmp": "图片文件",
    ".tiff": "图片文件",
    ".tif": "图片文件"
  },
  "libraries": {
    "pdf": true,
    "word": true,
    "excel": true,
    "powerpoint": true,
    "ocr": true
  },
  "message": "获取支持格式成功"
}
```

### 4. 批量解析
```
POST /api/v1/file-parser/batch-parse/
```

**参数：**
- `files`: 多个文件
- `encoding`: 文件编码（可选，默认utf-8）

**响应：**
```json
{
  "success": true,
  "total_files": 3,
  "success_count": 2,
  "failed_count": 1,
  "results": [
    {
      "filename": "doc1.pdf",
      "success": true,
      "file_size": 1024000,
      "md_content": "# 文档1\n\n内容..."
    },
    {
      "filename": "doc2.docx",
      "success": true,
      "file_size": 2048000,
      "md_content": "# 文档2\n\n内容..."
    },
    {
      "filename": "doc3.txt",
      "success": false,
      "error": "不支持的文件格式"
    }
  ],
  "message": "批量解析完成，成功 2 个文件"
}
```

### 5. 自定义选项解析
```
POST /api/v1/file-parser/parse-with-options/
```

**参数：**
- `file`: 上传的文件
- `encoding`: 文件编码（可选，默认utf-8）
- `include_tables`: 是否包含表格（可选，默认true）
- `include_images`: 是否包含图片（可选，默认true）
- `ocr_language`: OCR语言（可选，默认chi_sim+eng）

## 使用示例

### Python 客户端示例

```python
import requests

# 解析单个文件
def parse_file(file_path):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        response = requests.post(
            'http://localhost:8000/api/v1/file-parser/parse-file/',
            files=files,
            headers={'Authorization': 'Bearer your_token'}
        )
    return response.json()

# 批量解析
def batch_parse_files(file_paths):
    files = []
    for path in file_paths:
        files.append(('files', open(path, 'rb')))
    
    response = requests.post(
        'http://localhost:8000/api/v1/file-parser/batch-parse/',
        files=files,
        headers={'Authorization': 'Bearer your_token'}
    )
    return response.json()
```

### JavaScript 客户端示例

```javascript
// 解析单个文件
async function parseFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/v1/file-parser/parse-file/', {
    method: 'POST',
    body: formData,
    headers: {
      'Authorization': 'Bearer your_token'
    }
  });
  
  return response.json();
}

// 批量解析
async function batchParseFiles(files) {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });
  
  const response = await fetch('/api/v1/file-parser/batch-parse/', {
    method: 'POST',
    body: formData,
    headers: {
      'Authorization': 'Bearer your_token'
    }
  });
  
  return response.json();
}
```

## 依赖库

### 必需依赖
```bash
pip install pdfplumber==0.10.3
pip install python-docx==1.1.0
pip install openpyxl==3.1.2
pip install python-pptx==0.6.23
pip install pytesseract==0.3.10
pip install Pillow==10.2.0
pip install opencv-python==4.9.0.80
pip install beautifulsoup4==4.13.3
pip install pandas==2.2.3
```

### 系统依赖
- **Tesseract OCR**: 用于图片文字识别
  - Ubuntu/Debian: `sudo apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`
  - Windows: 下载并安装 Tesseract

## 配置说明

### OCR 配置
- 支持的语言：中文简体、英文、中文+英文
- 可配置的OCR参数：语言、页面分割模式等

### 文件大小限制
- 单个文件：最大50MB
- 批量处理：总大小最大100MB，最多10个文件

### 编码支持
- UTF-8（默认）
- GBK
- GB2312
- 自动编码检测

## 错误处理

### 常见错误
1. **文件格式不支持**: 返回400错误，包含不支持的文件扩展名
2. **文件过大**: 返回413错误，提示文件大小限制
3. **解析失败**: 返回500错误，包含具体错误信息
4. **依赖库缺失**: 返回500错误，提示缺少必要的解析库

### 错误响应格式
```json
{
  "detail": "错误描述信息"
}
```

## 性能优化

### 1. 异步处理
- 大文件使用异步处理
- 支持进度跟踪
- 可取消长时间运行的任务

### 2. 缓存机制
- 解析结果缓存
- 文件信息缓存
- 减少重复解析

### 3. 内存管理
- 流式处理大文件
- 及时释放临时文件
- 内存使用监控

## 安全考虑

### 1. 文件验证
- 文件类型验证
- 文件大小限制
- 恶意文件检测

### 2. 权限控制
- 用户认证
- 访问权限验证
- 操作日志记录

### 3. 数据保护
- 临时文件安全删除
- 敏感信息过滤
- 数据传输加密

## 扩展开发

### 添加新的文件格式支持

1. 在 `FileParserService` 类中添加新的解析方法
2. 更新 `supported_formats` 字典
3. 在 `parse_file` 方法中添加新的文件类型判断
4. 添加相应的依赖库到 requirements.txt

### 示例：添加 RTF 格式支持

```python
def _parse_rtf(self, file_path: str, **kwargs) -> str:
    """解析RTF文件"""
    try:
        import striprtf
        from striprtf.striprtf import rtf_to_text
        
        with open(file_path, 'r', encoding='utf-8') as file:
            rtf_content = file.read()
        
        text_content = rtf_to_text(rtf_content)
        
        md_content = []
        md_content.append(f"# {Path(file_path).stem}\n")
        md_content.append("**文档信息**: RTF文档\n\n")
        md_content.append(text_content)
        
        return "\n".join(md_content)
    except ImportError:
        raise ImportError("RTF解析库未安装，请安装 striprtf")
```

## 故障排除

### 常见问题

1. **OCR 识别失败**
   - 检查 Tesseract 是否正确安装
   - 确认语言包是否安装
   - 检查图片质量和清晰度

2. **PDF 解析失败**
   - 确认 PDF 文件是否损坏
   - 检查 PDF 是否加密
   - 验证 pdfplumber 版本兼容性

3. **Word 文档解析问题**
   - 确认文档格式是否支持
   - 检查文档是否损坏
   - 验证 python-docx 版本

4. **内存不足**
   - 减少批量处理的文件数量
   - 增加系统内存
   - 优化文件处理流程

### 日志调试

启用详细日志记录：
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 更新日志

### v1.0.0 (2024-01-01)
- 初始版本发布
- 支持PDF、Word、Excel、PowerPoint、图片格式
- 基础OCR功能
- 批量处理支持

### 计划功能
- 更多文件格式支持
- 高级OCR配置
- 云端处理支持
- 实时协作功能 