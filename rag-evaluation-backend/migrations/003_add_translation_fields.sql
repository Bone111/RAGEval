-- 添加翻译模型相关字段
-- 执行时间: 2025-01-13

-- 添加翻译模型标识字段
ALTER TABLE model_info 
ADD COLUMN is_translation_model BOOLEAN DEFAULT FALSE;

-- 添加翻译优先级字段
ALTER TABLE model_info 
ADD COLUMN translation_priority INTEGER DEFAULT 0;

-- 创建索引以提高查询性能
CREATE INDEX idx_model_info_translation_model ON model_info(is_translation_model);
CREATE INDEX idx_model_info_translation_priority ON model_info(translation_priority);

-- 添加注释
COMMENT ON COLUMN model_info.is_translation_model IS '是否为翻译专用模型';
COMMENT ON COLUMN model_info.translation_priority IS '翻译优先级，数字越大优先级越高';
