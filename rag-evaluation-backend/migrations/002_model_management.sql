-- =====================================================
-- 大模型统一管理系统 - 数据库迁移脚本
-- 版本: v1.0
-- 创建时间: 2025-10-11
-- 说明: 新增大模型统一管理相关表
-- =====================================================

-- =====================================================
-- 1. 大模型信息表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_info (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- 基础信息
    model_id VARCHAR(255) NOT NULL,
    model_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    model_type VARCHAR(50) NOT NULL, -- local, api, download, cloud
    model_source VARCHAR(100), -- huggingface, modelscope, openai, ollama等
    
    -- 模型详细信息
    model_family VARCHAR(100), -- llama, qwen, gpt, etc
    model_size VARCHAR(50), -- 7B, 13B, 70B, etc
    parameter_count BIGINT, -- 参数量
    model_version VARCHAR(100), -- 模型版本
    
    -- 路径和配置信息
    model_path VARCHAR(1000), -- 本地路径或URL
    config_path VARCHAR(1000), -- 配置文件路径
    tokenizer_path VARCHAR(1000), -- tokenizer路径
    
    -- API配置（如果是API模型）
    api_url VARCHAR(500),
    api_key VARCHAR(500),
    api_provider VARCHAR(100), -- openai, anthropic, etc
    
    -- 模型状态
    status VARCHAR(50) DEFAULT 'unknown', -- available, downloading, error, offline
    download_progress FLOAT DEFAULT 0.0, -- 下载进度 0-100
    file_size BIGINT, -- 文件大小（字节）
    disk_usage BIGINT, -- 磁盘占用（字节）
    
    -- 性能信息
    supported_context_length INTEGER, -- 支持的上下文长度
    max_tokens INTEGER, -- 最大生成tokens
    inference_speed FLOAT, -- 推理速度 tokens/s
    memory_usage BIGINT, -- 内存使用（字节）
    
    -- 能力标签
    capabilities JSONB DEFAULT '[]', -- ['chat', 'code', 'math', 'multimodal']
    languages JSONB DEFAULT '[]', -- 支持的语言
    tags JSONB DEFAULT '[]', -- 用户标签
    
    -- 使用统计
    usage_count INTEGER DEFAULT 0, -- 使用次数
    last_used_at TIMESTAMP, -- 最后使用时间
    
    -- 评测信息
    benchmark_scores JSONB DEFAULT '{}', -- 各项benchmark得分
    quality_rating FLOAT, -- 质量评分 1-10
    
    -- 系统信息
    is_active BOOLEAN DEFAULT true,
    is_favorite BOOLEAN DEFAULT false, -- 收藏
    notes TEXT, -- 用户备注
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TIMESTAMP, -- 最后扫描时间
    
    -- 额外元数据
    extra_metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE model_info IS '大模型信息统一管理表';
COMMENT ON COLUMN model_info.model_type IS 'local, api, download, cloud';
COMMENT ON COLUMN model_info.status IS 'available, downloading, error, offline, unknown';

-- =====================================================
-- 2. 模型使用日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_usage_logs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    model_id INTEGER REFERENCES model_info(id) ON DELETE CASCADE,
    
    -- 使用信息
    usage_type VARCHAR(50) NOT NULL, -- chat, eval, generation, etc
    task_name VARCHAR(255), -- 任务名称
    
    -- 性能数据
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms FLOAT, -- 延迟毫秒
    throughput FLOAT, -- tokens/s
    
    -- 成本统计
    cost_estimate FLOAT, -- 预估成本
    
    -- 质量评估
    quality_score FLOAT, -- 输出质量评分
    user_rating INTEGER, -- 用户评分 1-5
    
    -- 时间信息
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 额外信息
    extra_data JSONB DEFAULT '{}'
);

COMMENT ON TABLE model_usage_logs IS '模型使用日志表';

-- =====================================================
-- 3. 模型下载任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_download_tasks (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- 下载信息
    model_name VARCHAR(255) NOT NULL,
    model_source VARCHAR(100) NOT NULL, -- huggingface, modelscope, etc
    source_url VARCHAR(1000) NOT NULL, -- 下载源URL
    local_path VARCHAR(1000), -- 本地保存路径
    
    -- 任务状态
    status VARCHAR(50) DEFAULT 'pending', -- pending, downloading, completed, failed, cancelled
    progress FLOAT DEFAULT 0.0, -- 下载进度 0-100
    
    -- 文件信息
    total_size BIGINT, -- 总大小
    downloaded_size BIGINT DEFAULT 0, -- 已下载大小
    download_speed FLOAT, -- 下载速度 bytes/s
    
    -- 时间信息
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion TIMESTAMP, -- 预计完成时间
    
    -- 错误信息
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    
    -- 系统信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 额外配置
    download_config JSONB DEFAULT '{}'
);

COMMENT ON TABLE model_download_tasks IS '模型下载任务表';
COMMENT ON COLUMN model_download_tasks.status IS 'pending, downloading, completed, failed, cancelled';

-- =====================================================
-- 4. 本地模型注册表
-- =====================================================
CREATE TABLE IF NOT EXISTS local_model_registry (
    id SERIAL PRIMARY KEY,
    
    -- 模型路径信息
    model_path VARCHAR(1000) NOT NULL UNIQUE,
    model_name VARCHAR(255) NOT NULL,
    model_type VARCHAR(50), -- 推断的模型类型
    
    -- 文件信息
    file_size BIGINT,
    file_count INTEGER,
    config_files JSONB DEFAULT '[]', -- 配置文件列表
    
    -- 扫描信息
    scan_status VARCHAR(50) DEFAULT 'discovered', -- discovered, analyzed, registered, error
    last_modified TIMESTAMP, -- 文件最后修改时间
    last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 模型信息（从配置文件中提取）
    detected_info JSONB DEFAULT '{}', -- 检测到的模型信息
    
    -- 系统信息
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE local_model_registry IS '本地模型注册表 - 扫描发现的本地模型';
COMMENT ON COLUMN local_model_registry.scan_status IS 'discovered, analyzed, registered, error';

-- =====================================================
-- 5. 模型分类表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(100),
    color VARCHAR(20),
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE model_categories IS '模型分类表';

-- =====================================================
-- 6. 模型分类映射表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_category_mappings (
    id SERIAL PRIMARY KEY,
    model_id INTEGER REFERENCES model_info(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES model_categories(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(model_id, category_id)
);

COMMENT ON TABLE model_category_mappings IS '模型分类映射表';

-- =====================================================
-- 创建索引
-- =====================================================

-- model_info 索引
CREATE INDEX idx_model_info_user_id ON model_info(user_id);
CREATE INDEX idx_model_info_model_type ON model_info(model_type);
CREATE INDEX idx_model_info_status ON model_info(status);
CREATE INDEX idx_model_info_model_source ON model_info(model_source);
CREATE INDEX idx_model_info_is_active ON model_info(is_active);
CREATE INDEX idx_model_info_is_favorite ON model_info(is_favorite);
CREATE INDEX idx_model_info_created_at ON model_info(created_at DESC);
CREATE INDEX idx_model_info_last_used_at ON model_info(last_used_at DESC);

-- model_usage_logs 索引
CREATE INDEX idx_model_usage_logs_user_id ON model_usage_logs(user_id);
CREATE INDEX idx_model_usage_logs_model_id ON model_usage_logs(model_id);
CREATE INDEX idx_model_usage_logs_usage_type ON model_usage_logs(usage_type);
CREATE INDEX idx_model_usage_logs_created_at ON model_usage_logs(created_at DESC);
CREATE INDEX idx_model_usage_logs_started_at ON model_usage_logs(started_at DESC);

-- model_download_tasks 索引
CREATE INDEX idx_model_download_tasks_user_id ON model_download_tasks(user_id);
CREATE INDEX idx_model_download_tasks_status ON model_download_tasks(status);
CREATE INDEX idx_model_download_tasks_model_source ON model_download_tasks(model_source);
CREATE INDEX idx_model_download_tasks_created_at ON model_download_tasks(created_at DESC);

-- local_model_registry 索引
CREATE INDEX idx_local_model_registry_model_name ON local_model_registry(model_name);
CREATE INDEX idx_local_model_registry_model_type ON local_model_registry(model_type);
CREATE INDEX idx_local_model_registry_scan_status ON local_model_registry(scan_status);
CREATE INDEX idx_local_model_registry_last_scanned ON local_model_registry(last_scanned DESC);

-- model_categories 索引
CREATE INDEX idx_model_categories_name ON model_categories(name);
CREATE INDEX idx_model_categories_is_active ON model_categories(is_active);
CREATE INDEX idx_model_categories_sort_order ON model_categories(sort_order);

-- model_category_mappings 索引
CREATE INDEX idx_model_category_mappings_model_id ON model_category_mappings(model_id);
CREATE INDEX idx_model_category_mappings_category_id ON model_category_mappings(category_id);

-- =====================================================
-- 触发器 - 更新 updated_at 字段
-- =====================================================

-- 为 model_info 表添加触发器
DROP TRIGGER IF EXISTS update_model_info_updated_at ON model_info;
CREATE TRIGGER update_model_info_updated_at
    BEFORE UPDATE ON model_info
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 model_download_tasks 表添加触发器
DROP TRIGGER IF EXISTS update_model_download_tasks_updated_at ON model_download_tasks;
CREATE TRIGGER update_model_download_tasks_updated_at
    BEFORE UPDATE ON model_download_tasks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 local_model_registry 表添加触发器
DROP TRIGGER IF EXISTS update_local_model_registry_updated_at ON local_model_registry;
CREATE TRIGGER update_local_model_registry_updated_at
    BEFORE UPDATE ON local_model_registry
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 插入默认分类数据
-- =====================================================
INSERT INTO model_categories (name, display_name, description, icon, color, sort_order) VALUES
('language_models', '语言模型', '通用大语言模型', 'language', '#1890ff', 1),
('code_models', '代码模型', '专门用于代码生成和理解的模型', 'code', '#52c41a', 2),
('multimodal_models', '多模态模型', '支持图像、文本等多模态输入的模型', 'picture', '#722ed1', 3),
('embedding_models', '嵌入模型', '文本嵌入和向量化模型', 'deployment-unit', '#fa8c16', 4),
('math_models', '数学模型', '专门用于数学推理的模型', 'calculator', '#eb2f96', 5),
('chat_models', '对话模型', '针对对话场景优化的模型', 'comment', '#13c2c2', 6),
('local_models', '本地模型', '本地部署的模型', 'desktop', '#faad14', 7),
('api_models', 'API模型', '通过API调用的云端模型', 'cloud', '#2f54eb', 8)
ON CONFLICT (name) DO NOTHING;

-- =====================================================
-- 完成消息
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE '大模型统一管理系统数据表创建完成!';
    RAISE NOTICE '  1. model_info - 大模型信息统一管理表';
    RAISE NOTICE '  2. model_usage_logs - 模型使用日志表';
    RAISE NOTICE '  3. model_download_tasks - 模型下载任务表';
    RAISE NOTICE '  4. local_model_registry - 本地模型注册表';
    RAISE NOTICE '  5. model_categories - 模型分类表';
    RAISE NOTICE '  6. model_category_mappings - 模型分类映射表';
END $$;
