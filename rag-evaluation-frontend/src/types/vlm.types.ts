// VLM多模态评测相关类型定义

export interface VLMTaskCreate {
  task_name: string;
  model_id: string;
  datasets: string[];
  model_type?: string;
  api_base?: string;
  api_key?: string;
  model_path?: string;
  eval_backend?: string;
  limit?: number;
  nproc?: number;
  temperature?: number;
  max_tokens?: number;
  reuse_cache?: boolean;
  extra_config?: Record<string, any>;
}

export interface VLMTaskResponse {
  id: string;
  user_id: string;
  task_name: string;
  model_id: string;
  datasets: string[];
  status: string;
  progress: number;
  model_type?: string;
  model_path?: string;
  api_base?: string;
  eval_backend: string;
  limit?: number;
  nproc: number;
  temperature: number;
  max_tokens: number;
  reuse_cache: boolean;
  work_dir?: string;
  celery_task_id?: string;
  error_message?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface VLMResultResponse {
  id: string;
  task_id: string;
  dataset: string;
  metric_name: string;
  metric_value?: number;
  category?: string;
  subset_name?: string;
  num_samples?: number;
  accuracy?: number;
  raw_results?: Record<string, any>;
}

export interface VLMTaskDetail extends VLMTaskResponse {
  results: VLMResultResponse[];
}

export interface VLMDatasetInfo {
  name: string;
  display_name: string;
  description: string;
  category: string;
  language: string;
  num_samples?: number;
  supported_metrics: string[];
}

export interface VLMModelInfo {
  name: string;
  display_name: string;
  description: string;
  model_type: string;
  supported_modalities: string[];
  max_tokens: number;
  requires_api_key: boolean;
}

export interface VLMTaskStats {
  total_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
  average_duration_minutes?: number;
  popular_datasets: Array<{
    name: string;
    usage_count: number;
  }>;
  popular_models: Array<{
    name: string;
    usage_count: number;
  }>;
}

// VLM评测状态
export type VLMTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

// VLM模型类型
export type VLMModelType = 'local' | 'api' | 'custom';

// VLM数据集类别
export type VLMDatasetCategory = 
  | '综合理解' 
  | '感知推理' 
  | '视觉理解' 
  | '综合能力' 
  | '学科知识' 
  | '数学视觉' 
  | 'OCR识别' 
  | '图表分析' 
  | '图表理解' 
  | '其他';

// VLM指标类型  
export type VLMMetricType = 
  | 'accuracy' 
  | 'score' 
  | 'perception_score' 
  | 'cognition_score' 
  | 'word_accuracy' 
  | 'edit_distance' 
  | 'relaxed_accuracy';


