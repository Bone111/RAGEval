-- 添加时间追踪字段
-- 用于更准确地计算任务执行时长（排除暂停时间）

ALTER TABLE evalscope_tasks 
ADD COLUMN first_started_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN total_paused_duration INTEGER DEFAULT 0;

-- 为现有任务设置默认值
UPDATE evalscope_tasks 
SET first_started_at = started_at 
WHERE started_at IS NOT NULL;

-- 添加注释
COMMENT ON COLUMN evalscope_tasks.first_started_at IS '首次开始时间，用于计算总执行时长';
COMMENT ON COLUMN evalscope_tasks.total_paused_duration IS '总暂停时长（秒），用于计算有效执行时长';
