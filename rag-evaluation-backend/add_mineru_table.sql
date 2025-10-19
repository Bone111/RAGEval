-- 添加MinerU配置表
CREATE TABLE IF NOT EXISTS user_mineru_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    base_url VARCHAR(255) NOT NULL DEFAULT 'https://mineru.net/api/v4',
    api_key VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_mineru_configs_user_id ON user_mineru_configs(user_id);
CREATE INDEX IF NOT EXISTS idx_user_mineru_configs_active ON user_mineru_configs(is_active);

-- 添加唯一约束，确保每个用户只有一个活跃的配置
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_mineru_configs_user_active 
ON user_mineru_configs(user_id) WHERE is_active = TRUE;
