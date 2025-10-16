# RAG评测系统集成MinerU的实现方案

## 1. 项目概述

RAGEval是一个专业的RAG（检索增强生成）系统评测工具，MinerU作为一个高质量的文档解析工具，被集成到该系统中用于处理复杂文档格式（PDF、Word、PPT等），将其转换为高质量的Markdown格式，为后续的问答对生成和评测提供优质的文本数据。

## 2. 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 React    │    │  后端 FastAPI   │    │  MinerU API     │
│                 │    │                 │    │                 │
│ - 文件上传      │◄──►│ - API路由       │◄──►│ - 文档解析      │
│ - 解析状态监控  │    │ - 任务管理      │    │ - OCR识别       │
│ - 结果预览      │    │ - 缓存管理      │    │ - 公式识别      │
│ - 缓存管理      │    │ - 文件处理      │    │ - 表格提取      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  本地缓存系统   │
                    │                 │
                    │ - 文件缓存      │
                    │ - 解析结果缓存  │
                    │ - 静态文件服务  │
                    └─────────────────┘
```

## 3. MinerU核心功能集成

### 3.1 文档解析API

#### 实现位置
- **后端API**: `app/api/api_v1/endpoints/mineru_convert.py`
- **前端调用**: `QuestionGenerationContent.tsx`
- **测试脚本**: `test_mineru_async.py`

#### 核心API接口
```python
@router.post("/mineru-upload-and-parse")
async def mineru_upload_and_parse(
    file: UploadFile = File(..., description="要上传并解析的文件"),
    token: str = Form(..., description="Mineru在线API的token"),
    is_ocr: bool = Form(True, description="是否启用OCR"),
    enable_formula: bool = Form(True, description="是否启用公式识别")
):
    """
    MinerU文档解析主接口
    
    功能特点:
    1. 支持本地缓存机制，避免重复解析
    2. 异步处理，支持长时间解析任务
    3. 自动下载和解压解析结果
    4. 提取Markdown内容和相关文件
    """
```

#### 解析流程实现
```python
def mineru_parse_workflow(file, token, is_ocr, enable_formula):
    """
    MinerU解析工作流程
    
    Step 1: 缓存检查
    - 检查本地是否已有解析结果
    - 基于文件名（去扩展名）创建缓存目录
    - 如果命中缓存，直接返回本地结果
    
    Step 2: 获取上传URL
    - 调用MinerU API获取文件上传URL
    - 配置解析参数（OCR、公式识别、表格提取等）
    - 获取批次ID用于后续状态查询
    
    Step 3: 文件上传
    - 将文件上传到MinerU服务器
    - 处理上传失败的异常情况
    
    Step 4: 状态轮询
    - 定期查询解析任务状态
    - 最多轮询120次，每次间隔2秒
    - 处理解析成功、失败和超时情况
    
    Step 5: 结果下载和处理
    - 下载解析结果ZIP文件
    - 解压到本地缓存目录
    - 提取Markdown内容和相关文件
    - 生成静态文件访问路径
    """
```

### 3.2 缓存管理系统

#### 缓存目录结构
```
static/
└── mineru_cache/
    ├── 文档名1/
    │   ├── document.md          # 主要Markdown内容
    │   ├── images/              # 提取的图片
    │   └── tables/              # 提取的表格
    ├── 文档名2/
    └── ...
```

#### 缓存机制实现
```python
def check_local_cache(filename):
    """
    本地缓存检查机制
    
    1. 基于文件名（去扩展名）创建缓存目录
    2. 检查目录是否存在且包含文件
    3. 如果命中缓存，直接读取本地结果
    4. 返回缓存的Markdown内容和文件列表
    """
    filename_no_ext = os.path.splitext(filename)[0]
    file_dir = os.path.join(STATIC_ROOT, "mineru_cache", filename_no_ext)
    
    if os.path.exists(file_dir) and has_files(file_dir):
        return load_cached_result(file_dir)
    
    return None

def save_to_cache(filename, zip_content):
    """
    保存解析结果到本地缓存
    
    1. 创建以文件名命名的缓存目录
    2. 解压ZIP文件到缓存目录
    3. 生成静态文件访问路径
    4. 提取Markdown内容
    """
```

#### 缓存清理API
```python
@router.post("/clear-mineru-cache")
def clear_mineru_cache():
    """
    清理MinerU解析缓存
    
    功能:
    1. 删除所有缓存目录和文件
    2. 重新创建空的缓存根目录
    3. 返回清理结果状态
    """
    try:
        STATIC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../static'))
        mineru_cache_dir = os.path.join(STATIC_ROOT, "mineru_cache")
        if os.path.exists(mineru_cache_dir):
            shutil.rmtree(mineru_cache_dir)
            os.makedirs(mineru_cache_dir, exist_ok=True)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

### 3.3 前端集成实现

#### 文件上传和解析
```typescript
const handleMineruParse = async () => {
    setParsingStatus('parsing');
    setParsingError(null);

    try {
        const files = fileList.map(file => file.originFileObj);
        const formData = new FormData();
        formData.append('file', files[0]);
        formData.append('token', MINERU_TOKEN);
        formData.append('is_ocr', 'true');
        formData.append('enable_formula', 'false');
        
        const response = await fetch('/api/v1/mineru/mineru-upload-and-parse', {
            method: 'POST',
            body: formData,
        });
        
        const data = await response.json();
        if (data && data.files) {
            setParsedFiles(data.files);
            setParsingStatus('success');
        } else {
            setParsingStatus('error');
            setParsingError(data.error || 'mineru解析失败');
        }
    } catch (err: any) {
        setParsingStatus('error');
        setParsingError(err.message || 'mineru解析异常');
    }
};
```

#### 状态管理
```typescript
// 解析状态类型定义
type ParsingStatus = 'idle' | 'parsing' | 'success' | 'error';

// 状态管理
const [parsingStatus, setParsingStatus] = useState<ParsingStatus>('idle');
const [parsedFiles, setParsedFiles] = useState<any[]>([]);
const [parsingError, setParsingError] = useState<string | null>(null);

// 解析结果处理
interface ParsedFile {
    filename: string;
    state: string;
    error_msg: string | null;
    success: boolean;
    md_text: string | null;
    extracted_files: string[];
}
```

#### 缓存管理UI
```typescript
const handleClearMineruCache = async () => {
    setClearCacheModalVisible(true);
};

const doClearMineruCache = async () => {
    try {
        const resp = await fetch('/api/v1/mineru/clear-mineru-cache', { 
            method: 'POST' 
        });
        const data = await resp.json();
        if (data.success) {
            message.success('mineru解析缓存已清理');
            setParsedFiles([]);
            setParsingStatus('idle');
        } else {
            message.error(data.error || '清理缓存失败');
        }
    } catch (e) {
        message.error('清理缓存请求失败');
    } finally {
        setClearCacheModalVisible(false);
    }
};
```

## 4. 技术特点

### 4.1 高质量文档解析
- **OCR识别**: 支持图片和扫描文档的文字识别
- **公式识别**: 准确识别和转换数学公式
- **表格提取**: 保持表格结构的完整性
- **图片处理**: 提取并保存文档中的图片资源

### 4.2 智能缓存机制
- **本地缓存**: 避免重复解析相同文档
- **文件完整性检查**: 确保缓存文件的有效性
- **静态文件服务**: 通过HTTP直接访问解析结果
- **缓存管理**: 支持手动清理缓存

### 4.3 异步处理架构
- **非阻塞解析**: 支持长时间的文档解析任务
- **状态轮询**: 实时监控解析进度
- **错误处理**: 完善的异常处理和重试机制
- **超时控制**: 防止无限等待的情况

### 4.4 用户体验优化
- **进度反馈**: 实时显示解析状态
- **结果预览**: 支持解析结果的预览和下载
- **错误提示**: 详细的错误信息和处理建议
- **批量处理**: 支持多文件的批量解析

## 5. 配置和部署

### 5.1 API配置
```python
# MinerU API配置
MINERU_API_BASE = "https://mineru.net/api/v4"
MINERU_TOKEN = "your_mineru_token_here"

# 解析参数配置
DEFAULT_PARSE_CONFIG = {
    "enable_formula": True,
    "language": "auto",
    "enable_table": True,
    "model_version": "v2",
    "is_ocr": True
}
```

### 5.2 缓存配置
```python
# 缓存目录配置
STATIC_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../static'))
MINERU_CACHE_DIR = os.path.join(STATIC_ROOT, "mineru_cache")

# 轮询配置
MAX_POLL_ATTEMPTS = 120  # 最大轮询次数
POLL_INTERVAL = 2        # 轮询间隔（秒）
```

### 5.3 前端配置
```typescript
// MinerU Token配置（实际使用中应从环境变量或配置文件读取）
const MINERU_TOKEN = process.env.REACT_APP_MINERU_TOKEN || 'default_token';

// API端点配置
const MINERU_API_ENDPOINTS = {
    parse: '/api/v1/mineru/mineru-upload-and-parse',
    clearCache: '/api/v1/mineru/clear-mineru-cache'
};
```

## 6. 使用流程

### 6.1 文档解析流程
1. **文件上传**: 用户通过前端界面上传文档文件
2. **缓存检查**: 系统首先检查是否已有解析缓存
3. **在线解析**: 如无缓存，调用MinerU API进行解析
4. **状态监控**: 实时显示解析进度和状态
5. **结果处理**: 下载解析结果并保存到本地缓存
6. **内容提取**: 提取Markdown内容和相关文件
7. **结果展示**: 在前端展示解析结果和文件列表

### 6.2 缓存管理流程
1. **缓存命中**: 检查本地是否已有相同文件的解析结果
2. **缓存存储**: 将新的解析结果保存到本地缓存
3. **缓存清理**: 支持手动清理所有缓存文件
4. **缓存验证**: 确保缓存文件的完整性和有效性

## 7. 错误处理和监控

### 7.1 错误类型
- **网络错误**: API请求失败、超时等
- **解析错误**: 文档格式不支持、解析失败等
- **缓存错误**: 文件读写失败、权限问题等
- **配置错误**: Token无效、参数错误等

### 7.2 监控指标
- **解析成功率**: 统计解析成功和失败的比例
- **解析时间**: 监控不同类型文档的解析耗时
- **缓存命中率**: 统计缓存使用效率
- **API调用频率**: 监控MinerU API的调用情况

## 8. 性能优化

### 8.1 缓存优化
- **智能缓存策略**: 基于文件内容哈希的缓存机制
- **缓存压缩**: 对大文件进行压缩存储
- **缓存清理策略**: 定期清理过期或无用的缓存
- **并发控制**: 避免同时解析相同文件

### 8.2 网络优化
- **请求重试**: 网络失败时的自动重试机制
- **连接池**: 复用HTTP连接提高效率
- **超时控制**: 合理设置请求超时时间
- **限流控制**: 避免过于频繁的API调用

## 9. 安全考虑

### 9.1 数据安全
- **Token管理**: 安全存储和使用MinerU API Token
- **文件验证**: 上传文件的格式和大小验证
- **路径安全**: 防止路径遍历攻击
- **权限控制**: 确保只有授权用户可以访问解析结果

### 9.2 隐私保护
- **数据传输**: 使用HTTPS加密传输
- **本地存储**: 敏感数据的本地加密存储
- **数据清理**: 及时清理临时文件和缓存
- **访问日志**: 记录文件访问和操作日志

## 10. 扩展性设计

### 10.1 多格式支持
- 支持更多文档格式（Excel、PPT等）
- 自定义解析参数配置
- 插件化的解析器架构

### 10.2 分布式部署
- 支持多实例部署
- 共享缓存机制
- 负载均衡和故障转移

### 10.3 API扩展
- 批量解析接口
- 异步回调机制
- Webhook通知功能
