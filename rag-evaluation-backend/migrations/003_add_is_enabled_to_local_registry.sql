-- =====================================================
-- 数据库迁移: 添加 is_enabled 字段到 local_model_registry 表
-- 版本: v1.1
-- 创建时间: 2025-10-12
-- 说明: 添加启用/禁用控制字段到本地模型注册表
-- =====================================================

-- 检查并添加 is_enabled 字段
DO $$
BEGIN
    -- 检查列是否已经存在
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'local_model_registry' 
        AND column_name = 'is_enabled'
    ) THEN
        -- 添加列
        ALTER TABLE local_model_registry 
        ADD COLUMN is_enabled BOOLEAN DEFAULT true;
        
        -- 添加注释
        COMMENT ON COLUMN local_model_registry.is_enabled IS '是否启用，控制是否显示在模型列表中';
        
        -- 创建索引（可选，用于提高查询性能）
        CREATE INDEX IF NOT EXISTS idx_local_model_registry_is_enabled 
        ON local_model_registry(is_enabled);
        
        RAISE NOTICE '✅ 成功添加 is_enabled 字段到 local_model_registry 表';
    ELSE
        RAISE NOTICE 'ℹ️ is_enabled 字段已存在，跳过迁移';
    END IF;
END $$;

-- =====================================================
-- 完成消息
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE '本地模型注册表迁移完成!';
    RAISE NOTICE '  - 添加了 is_enabled 字段用于控制模型显示';
    RAISE NOTICE '  - 默认值设置为 true（启用）';
    RAISE NOTICE '  - 所有现有记录默认为启用状态';
END $$;

