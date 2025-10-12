-- =====================================================
-- EvalScope 图形化界面 - 数据库迁移脚本
-- 版本: v1.1
-- 创建时间: 2025-10-09
-- 说明: 添加EvalScope评测功能相关表
--       修复 'metadata' 字段名冲突
-- =====================================================

-- =====================================================
-- 1. EvalScope评测任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS evalscope_tasks (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    model_args JSONB DEFAULT '{}',
    datasets TEXT[] NOT NULL,
    dataset_args JSONB DEFAULT '{}',
    generation_config JSONB DEFAULT '{}',
    eval_backend VARCHAR(50) DEFAULT 'Native',
    eval_type VARCHAR(50) DEFAULT 'checkpoint',
    status VARCHAR(50) DEFAULT 'pending',
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    work_dir VARCHAR(500),
    error_message TEXT,
    extra_metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE evalscope_tasks IS 'EvalScope评测任务表';
COMMENT ON COLUMN evalscope_tasks.status IS 'pending, running, completed, failed, cancelled';
COMMENT ON COLUMN evalscope_tasks.eval_backend IS 'Native, OpenCompass, VLMEvalKit, RAGEval';

-- =====================================================
-- 2. EvalScope评测结果表
-- =====================================================
CREATE TABLE IF NOT EXISTS evalscope_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES evalscope_tasks(id) ON DELETE CASCADE,
    benchmark VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT,
    category VARCHAR(100),
    subset_name VARCHAR(100),
    num_samples INTEGER,
    raw_results JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE evalscope_results IS 'EvalScope评测结果表';

-- =====================================================
-- 3. 性能测试任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS perf_test_tasks (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL,
    api_url VARCHAR(500) NOT NULL,
    api_key VARCHAR(500),
    model_name VARCHAR(255),
    test_type VARCHAR(50) DEFAULT 'single',
    parallel_configs INTEGER[] DEFAULT ARRAY[10],
    number_configs INTEGER[] DEFAULT ARRAY[100],
    duration INTEGER,
    stream BOOLEAN DEFAULT false,
    config JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    extra_metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE perf_test_tasks IS '性能测试任务表';
COMMENT ON COLUMN perf_test_tasks.test_type IS 'single, multi, speed_benchmark';

-- =====================================================
-- 4. 性能测试结果表
-- =====================================================
CREATE TABLE IF NOT EXISTS perf_test_results (
    id SERIAL PRIMARY KEY,
    task_id INTEGER REFERENCES perf_test_tasks(id) ON DELETE CASCADE,
    parallel INTEGER NOT NULL,
    number INTEGER NOT NULL,
    qps FLOAT,
    avg_latency FLOAT,
    ttft FLOAT,
    tpop FLOAT,
    throughput FLOAT,
    success_rate FLOAT,
    error_count INTEGER DEFAULT 0,
    percentile_50 FLOAT,
    percentile_90 FLOAT,
    percentile_95 FLOAT,
    percentile_99 FLOAT,
    raw_metrics JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE perf_test_results IS '性能测试结果表';

-- =====================================================
-- 5. 模型配置表
-- =====================================================
CREATE TABLE IF NOT EXISTS model_configs (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    model_id VARCHAR(255) NOT NULL,
    model_name VARCHAR(255),
    model_type VARCHAR(50) DEFAULT 'local',
    model_path VARCHAR(500),
    api_url VARCHAR(500),
    api_key VARCHAR(500),
    model_args JSONB DEFAULT '{}',
    generation_config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, model_id),
    extra_metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE model_configs IS '模型配置表';
COMMENT ON COLUMN model_configs.model_type IS 'local, api, modelscope, huggingface';

-- =====================================================
-- 6. 数据集缓存表
-- =====================================================
CREATE TABLE IF NOT EXISTS dataset_cache (
    id SERIAL PRIMARY KEY,
    dataset_name VARCHAR(255) NOT NULL UNIQUE,
    dataset_type VARCHAR(50) DEFAULT 'standard',
    category VARCHAR(100),
    language VARCHAR(50),
    num_samples INTEGER,
    cache_path VARCHAR(500),
    download_status VARCHAR(50) DEFAULT 'not_cached',
    size_mb FLOAT,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extra_metadata JSONB DEFAULT '{}'
);

COMMENT ON TABLE dataset_cache IS '数据集缓存表';
COMMENT ON COLUMN dataset_cache.download_status IS 'cached, downloading, failed, not_cached';

-- =====================================================
-- 7. 任务标签关联表
-- =====================================================
CREATE TABLE IF NOT EXISTS task_tags (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    task_id INTEGER NOT NULL,
    tag VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_type, task_id, tag)
);

COMMENT ON TABLE task_tags IS '任务标签关联表';
COMMENT ON COLUMN task_tags.task_type IS 'evalscope, perf, rag';

-- =====================================================
-- 8. 模型对比记录表 (移除)
-- =====================================================
-- DROP TABLE IF EXISTS model_comparisons;

-- =====================================================
-- 创建索引
-- =====================================================

-- evalscope_tasks 索引
CREATE INDEX idx_evalscope_tasks_user_id ON evalscope_tasks(user_id);
CREATE INDEX idx_evalscope_tasks_status ON evalscope_tasks(status);
CREATE INDEX idx_evalscope_tasks_created_at ON evalscope_tasks(created_at DESC);

-- evalscope_results 索引
CREATE INDEX idx_evalscope_results_task_id ON evalscope_results(task_id);
CREATE INDEX idx_evalscope_results_benchmark ON evalscope_results(benchmark);

-- perf_test_tasks 索引
CREATE INDEX idx_perf_test_tasks_user_id ON perf_test_tasks(user_id);
CREATE INDEX idx_perf_test_tasks_status ON perf_test_tasks(status);
CREATE INDEX idx_perf_test_tasks_created_at ON perf_test_tasks(created_at DESC);

-- perf_test_results 索引
CREATE INDEX idx_perf_test_results_task_id ON perf_test_results(task_id);

-- model_configs 索引
CREATE INDEX idx_model_configs_user_id ON model_configs(user_id);
CREATE INDEX idx_model_configs_is_active ON model_configs(is_active);

-- dataset_cache 索引
CREATE INDEX idx_dataset_cache_category ON dataset_cache(category);
CREATE INDEX idx_dataset_cache_status ON dataset_cache(download_status);

-- task_tags 索引
CREATE INDEX idx_task_tags_task ON task_tags(task_type, task_id);
CREATE INDEX idx_task_tags_tag ON task_tags(tag);

-- model_comparisons 索引 (移除)
-- DROP INDEX IF EXISTS idx_model_comparisons_user_id;

-- =====================================================
-- 初始化数据集元数据
-- =====================================================

-- 插入标准benchmark数据集信息
INSERT INTO dataset_cache (dataset_name, dataset_type, category, language, num_samples, download_status, extra_metadata) VALUES
    ('mmlu', 'standard', 'Knowledge', 'English', 14042, 'not_cached', '{"description": "大规模多任务语言理解", "tags": ["knowledge", "mcq"]}'),
    ('cmmlu', 'standard', 'Knowledge', 'Chinese', 11528, 'not_cached', '{"description": "中文多任务语言理解", "tags": ["knowledge", "mcq", "chinese"]}'),
    ('gsm8k', 'standard', 'Math', 'English', 1319, 'not_cached', '{"description": "小学数学应用题", "tags": ["math", "reasoning"]}'),
    ('arc', 'standard', 'Reasoning', 'English', 869, 'not_cached', '{"description": "AI2推理挑战", "tags": ["reasoning", "mcq"]}'),
    ('bbh', 'standard', 'Reasoning', 'English', 6511, 'not_cached', '{"description": "大模型困难推理", "tags": ["reasoning", "hard"]}'),
    ('humaneval', 'standard', 'Coding', 'English', 164, 'not_cached', '{"description": "代码生成评测", "tags": ["coding", "python"]}'),
    ('ceval', 'standard', 'Knowledge', 'Chinese', 12342, 'not_cached', '{"description": "中文评测基准", "tags": ["knowledge", "chinese"]}'),
    ('hellaswag', 'standard', 'Reasoning', 'English', 10042, 'not_cached', '{"description": "常识推理", "tags": ["commonsense", "reasoning"]}'),
    ('truthfulqa', 'standard', 'Truthfulness', 'English', 817, 'not_cached', '{"description": "真实性问答", "tags": ["truthfulness", "qa"]}'),
    ('gpqa', 'standard', 'Reasoning', 'English', 448, 'not_cached', '{"description": "专家问答", "tags": ["reasoning", "expert"]}')
ON CONFLICT (dataset_name) DO NOTHING;

-- =====================================================
-- 创建更新时间触发器函数
-- =====================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为 model_configs 表添加触发器
DROP TRIGGER IF EXISTS update_model_configs_updated_at ON model_configs;
CREATE TRIGGER update_model_configs_updated_at
    BEFORE UPDATE ON model_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- 授权 (可选，根据实际情况调整)
-- =====================================================

-- 如果有特定的应用用户，可以授权
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;

-- =====================================================
-- 迁移完成
-- =====================================================

-- 验证表创建
DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE 'EvalScope数据库迁移完成！';
    RAISE NOTICE '创建的表:';
    RAISE NOTICE '  1. evalscope_tasks - 评测任务表';
    RAISE NOTICE '  2. evalscope_results - 评测结果表';
    RAISE NOTICE '  3. perf_test_tasks - 性能测试任务表';
    RAISE NOTICE '  4. perf_test_results - 性能测试结果表';
    RAISE NOTICE '  5. model_configs - 模型配置表';
    RAISE NOTICE '  6. dataset_cache - 数据集缓存表';
    RAISE NOTICE '  7. task_tags - 任务标签表';
    RAISE NOTICE '  (model_comparisons - 模型对比表 已移除)';
    RAISE NOTICE '=====================================================';
END $$;

