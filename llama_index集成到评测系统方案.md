# LlamaIndex集成到RAG评测系统实现方案

## 1. 项目概述

RAGEval是一个专业的RAG（检索增强生成）系统评测工具，提供从数据准备、自动评测到报告生成的全流程解决方案。本方案详细描述了LlamaIndex在该评测系统中的集成实现逻辑。

## 2. 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 React    │    │  后端 FastAPI   │    │  LlamaIndex     │
│                 │    │                 │    │                 │
│ - 文件上传      │◄──►│ - API路由       │◄──►│ - 文档分块      │
│ - 分块配置      │    │ - 业务逻辑      │    │ - 问答生成      │
│ - 问答生成      │    │ - 数据处理      │    │ - 评测数据集    │
│ - 结果展示      │    │ - 数据库操作    │    │ - CustomLLM     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 3. LlamaIndex核心功能集成

### 3.1 文档分块功能

#### 实现位置
- **后端**: `app/services/llm_service.py` - `llamaindex_split_files()`
- **API**: `app/api/api_v1/endpoints/llamaindex_split.py`
- **前端**: `QuestionGeneratorService.ts` - `processContentFilesWithLlamaIndex()`

#### 核心实现逻辑
```python
def llamaindex_split_files(files: List[dict], chunk_size: int = 2048, chunk_overlap: int = 50, include_metadata: bool = False):
    """
    使用LlamaIndex的SentenceSplitter进行文档分块
    
    参数:
    - files: 文件列表，包含name和content
    - chunk_size: 分块大小，默认2048字符
    - chunk_overlap: 重叠大小，默认50字符
    - include_metadata: 是否包含元数据
    
    返回:
    - 分块列表，每个分块包含id、content、tokens、selected、fileName
    """
    all_chunks = []
    for file in files:
        parser = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            include_metadata=include_metadata
        )
        chunks = parser.split_text(file['content'])
        for chunk in chunks:
            all_chunks.append({
                "id": str(uuid.uuid4()),
                "content": chunk,
                "tokens": len(chunk),
                "selected": True,
                "fileName": file['name']
            })
    return all_chunks
```

#### API接口设计
```python
@router.post("/llamaindex_split")
async def llamaindex_split(req: SplitRequest):
    """
    LlamaIndex分块API接口
    
    请求体:
    - files: 文件内容列表
    - chunk_size: 分块大小
    - chunk_overlap: 重叠大小
    - include_metadata: 是否包含元数据
    """
    return llamaindex_split_files(
        [file.dict() for file in req.files],
        req.chunk_size,
        req.chunk_overlap,
        req.include_metadata
    )
```

### 3.2 问答对生成功能

#### 实现位置
- **独立脚本**: `gen_test_data.py`
- **核心类**: `SafeSyncHTTPLLM` (CustomLLM实现)
- **生成器**: `RagDatasetGenerator`

#### CustomLLM实现
```python
class SafeSyncHTTPLLM(CustomLLM):
    """
    自定义LLM实现，支持多种API格式
    - 支持Ollama本地API
    - 支持OpenAI兼容API
    - 支持阿里云DashScope API
    """
    endpoint: str = Field(..., description="API endpoint URL")
    model: str = Field(..., description="Model name")
    temperature: float = Field(default=0.6)
    top_p: float = Field(default=0.95)
    max_tokens: int = Field(default=1024)
    timeout: int = Field(default=30)
    api_key: str = Field(default="")

    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """
        核心完成方法，处理不同API格式的请求和响应
        - 自动识别Ollama和OpenAI格式
        - 支持流式和非流式响应
        - 错误处理和重试机制
        """
```

#### 数据集生成流程
```python
def generate_safe_dataset(docs_path: str, output_file: str):
    """
    安全生成评测数据集的完整流程
    
    1. 文档加载和验证
    2. 使用SentenceSplitter进行分块
    3. 初始化CustomLLM
    4. 使用RagDatasetGenerator生成问答对
    5. 数据清洗和格式化
    6. 保存为JSON格式
    """
    # 1. 文档加载
    documents = SimpleDirectoryReader(
        input_files=[docs_path],
        file_metadata=lambda _: {}
    ).load_data()
    
    # 2. 文档分块
    parser = SentenceSplitter(
        chunk_size=2048,
        chunk_overlap=50,
        include_metadata=False
    )
    nodes = parser.get_nodes_from_documents(documents)
    
    # 3. 初始化LLM
    llm = SafeSyncHTTPLLM(
        endpoint="http://localhost:11434/api/generate",
        model="qwen3:4b",
        timeout=60
    )
    
    # 4. 生成数据集
    generator = RagDatasetGenerator(
        nodes=nodes,
        llm=llm,
        num_questions_per_chunk=10,
        question_gen_query="生成10个清晰的问题..."
    )
    dataset = generator.generate_dataset_from_nodes()
    
    # 5. 数据清洗和保存
    for example in dataset.examples:
        example.query = extract_real_question(example.query)
    
    save_dataset(dataset, output_file)
```

### 3.3 前端集成

#### 分块模式选择
```typescript
// 前端支持两种分块模式
const [splitMode, setSplitMode] = useState<'langchain' | 'llamaindex'>('langchain');

// LlamaIndex分块调用
public async processContentFilesWithLlamaIndex(
    contentFiles: {name: string, content: string}[], 
    chunkSize?: number
): Promise<TextChunk[]> {
    const response = await fetch('/api/v1/llamaindex_split', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            files: contentFiles,
            chunk_size: chunkSize || 2048,
            chunk_overlap: 50,
            include_metadata: false,
        }),
    });
    
    if (!response.ok) {
        throw new Error('LlamaIndex分块API请求失败');
    }
    
    return await response.json();
}
```

## 4. 技术特点

### 4.1 多API兼容性
- **Ollama本地部署**: 支持流式响应处理
- **OpenAI兼容API**: 标准chat/completions格式
- **阿里云DashScope**: 兼容阿里云API格式

### 4.2 错误处理机制
- 请求超时处理
- API响应格式自动识别
- 异常情况下的降级处理
- UTF-8编码保证

### 4.3 性能优化
- 并发请求控制
- 分块大小可配置
- 内存使用优化
- 进度实时反馈

## 5. 部署配置

### 5.1 依赖安装
```bash
# 后端依赖
pip install llama-index-core>=0.12.0,<0.13.0
pip install llama-index>=0.12.0,<0.13.0
pip install llama-index-embeddings-huggingface

# 前端无需额外依赖，通过API调用
```

### 5.2 配置文件
```json
{
    "dashscope_api_key": "your_api_key_here",
    "ollama_endpoint": "http://localhost:11434/api/generate",
    "default_model": "qwen3:4b"
}
```

## 6. 使用流程

### 6.1 文档分块流程
1. 用户上传文档文件
2. 前端选择LlamaIndex分块模式
3. 配置分块参数（大小、重叠等）
4. 调用后端API进行分块处理
5. 返回分块结果供用户预览和选择

### 6.2 问答生成流程
1. 基于分块结果生成问答对
2. 使用CustomLLM调用配置的大模型
3. 通过RagDatasetGenerator批量生成
4. 自动清洗和格式化问答内容
5. 保存为标准评测数据集格式

## 7. 扩展性设计

### 7.1 模块化架构
- 分块逻辑独立封装
- LLM接口标准化
- 数据格式统一

### 7.2 可配置性
- 支持多种分块策略
- 灵活的LLM配置
- 可定制的问答生成模板

### 7.3 监控和日志
- 详细的处理日志
- 性能指标监控
- 错误追踪和报告

## 8. 未来优化方向

1. **向量化支持**: 集成embedding模型进行语义分块
2. **评测指标扩展**: 增加更多LlamaIndex评测指标
3. **批处理优化**: 支持大规模文档的批量处理
4. **缓存机制**: 添加分块和生成结果的缓存
5. **多语言支持**: 扩展对多语言文档的处理能力
