/**
 * EvalScope评测相关类型定义
 */

// ========== 任务相关 ==========

export interface EvalTask {
  id: number;
  user_id: number;
  task_name: string;
  model_id: string;
  datasets: string[];
  status: TaskStatus;
  progress: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  model_args?: Record<string, any>;
  dataset_args?: Record<string, any>;
  generation_config?: Record<string, any>;
  eval_backend?: string;
  eval_type?: string;
  extra_metadata?: Record<string, any>;
}

export interface EvalTaskDetail extends EvalTask {
  model_args: Record<string, any>;
  dataset_args: Record<string, any>;
  generation_config: Record<string, any>;
  eval_backend: string;
  eval_type?: string;
  work_dir?: string;
  metadata: Record<string, any>;
  extra_metadata?: Record<string, any>;
  results?: EvalResult[];
}

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused';

export interface ModelConfig {
  type: string;
  base_url: string;
  api_key?: string;
  model_name: string;
  additional_params?: Record<string, any>;
}

export interface TaskCreateRequest {
  task_name: string;
  model_id: string;
  datasets: string[];
  model_args?: Record<string, any>;
  dataset_args?: Record<string, any>;
  generation_config?: Record<string, any>;
  eval_backend?: string;
  eval_type?: string;
  limit?: number;
  model_config?: ModelConfig;
  user_model_config?: Record<string, any>;
}

export interface TaskListResponse {
  total: number;
  tasks: EvalTask[];
}

// ========== 结果相关 ==========

export interface EvalResult {
  id: number;
  task_id: number;
  benchmark: string;
  metric_name: string;
  metric_value?: number;
  category?: string;
  subset_name?: string;
  num_samples?: number;
  created_at: string;
}

export interface EvalResultDetail extends EvalResult {
  raw_results: Record<string, any>;
}

// ========== Benchmark相关 ==========

export interface BenchmarkInfo {
  name: string;
  description: string;
  category: string;
  language: string;
  num_samples?: number;
  tags: string[];
  cached: boolean;
}

export interface BenchmarkListResponse {
  total: number;
  benchmarks: BenchmarkInfo[];
}

// ========== WebSocket消息 ==========

export interface DatasetProgress {
  name: string;
  status: 'waiting' | 'running' | 'completed' | 'failed';
  progress: number;
  current_step?: string;
  total_samples?: number;
  completed_samples?: number;
  start_time?: string;
  end_time?: string;
}

export interface SubsetProgress {
  name: string;
  completed: number;
  total: number;
  progress: number;
  status: 'waiting' | 'running' | 'completed' | 'failed';
  last_updated?: string;
}

export interface DetailedProgress {
  overall_progress: number;
  current_dataset?: string;
  total_datasets: number;
  completed_datasets: number;
  dataset_progress: DatasetProgress[];
  subset_progress?: SubsetProgress[];  // 新增：子集进度
  message?: string;
  phase: 'initializing' | 'loading_model' | 'evaluating' | 'processing_results' | 'completed';
}

export interface ProgressUpdate {
  type: 'progress';
  task_id: number;
  progress: number;
  current_benchmark?: string;
  message?: string;
  detailed_progress?: DetailedProgress;
}

export interface LogMessage {
  type: 'log';
  task_id: number;
  level: 'info' | 'warning' | 'error';
  message: string;
  timestamp: string;
}

export interface ResultUpdate {
  type: 'result';
  task_id: number;
  benchmark: string;
  metric_name: string;
  metric_value: number;
}

export type WebSocketMessage = ProgressUpdate | LogMessage | ResultUpdate;

// ========== 模型配置 ==========

export interface ModelConfig {
  id?: number;
  model_id: string;
  model_name?: string;
  model_type: 'local' | 'api' | 'modelscope' | 'huggingface';
  model_path?: string;
  api_url?: string;
  api_key?: string;
  model_args?: Record<string, any>;
  generation_config?: Record<string, any>;
}

// ========== 对比分析 ==========

export interface ComparisonRequest {
  task_ids: number[];
  comparison_type?: 'detailed' | 'summary' | 'report';
  include_charts?: boolean;
  include_statistics?: boolean;
}

export interface ComparisonResponse {
  comparison_id: string;
  tasks: ComparisonTask[];
  comparison_data: ComparisonAnalysis;
  statistics: ComparisonStatistics;
  charts_data: ComparisonCharts;
  generated_at: string;
}

export interface ComparisonTask {
  task_id: number;
  task_name: string;
  model_id: string;
  model_type: string;
  datasets: string[];
  status: string;
  created_at: string;
  completed_at: string;
  progress: number;
  results: ComparisonResult[];
}

export interface ComparisonResult {
  id: number;
  benchmark: string;
  metric_name: string;
  metric_value?: number;
  category: string;
  subset_name: string;
  num_samples?: number;
  raw_results: Record<string, any>;
}

export interface ComparisonAnalysis {
  comparison_table: ComparisonTableRow[];
  win_rates: Record<string, number>;
  average_scores: Record<string, number>;
  datasets: string[];
  models: string[];
}

export interface ComparisonTableRow {
  benchmark: string;
  [modelId: string]: number | string | null;
}

export interface ComparisonStatistics {
  model_statistics: Record<string, ModelStats>;
  global_statistics: GlobalStats;
}

export interface ModelStats {
  average_score: number;
  max_score: number;
  min_score: number;
  score_count: number;
  score_std: number;
}

export interface GlobalStats {
  overall_average: number;
  overall_max: number;
  overall_min: number;
  total_scores: number;
  score_range: number;
  best_model?: {
    model_id: string;
    average_score: number;
  };
  worst_model?: {
    model_id: string;
    average_score: number;
  };
}

export interface ComparisonCharts {
  radar: {
    indicators: Array<{ name: string; max: number }>;
    series: Array<{ name: string; value: number[] }>;
  };
  bar: {
    datasets: string[];
    data: Array<{
      dataset: string;
      scores: number[];
      models: string[];
    }>;
  };
  heatmap: {
    xAxis: string[];
    yAxis: string[];
    data: Array<[number, number, number]>;
  };
}

export interface ComparisonData {
  id: number;
  comparison_name?: string;
  task_ids: number[];
  comparison_data: Record<string, any>;
  created_at: string;
}

// ========== Benchmark分类 ==========

export const BENCHMARK_CATEGORIES = [
  'Knowledge',
  'Math',
  'Reasoning',
  'Coding',
  'LongContext',
  'MultiModal',
  'RAG',
  'AIGC'
] as const;

export type BenchmarkCategory = typeof BENCHMARK_CATEGORIES[number];

// ========== Eval Backend ==========

export const EVAL_BACKENDS = [
  'Native',
  'OpenCompass',
  'VLMEvalKit',
  'RAGEval'
] as const;

export type EvalBackend = typeof EVAL_BACKENDS[number];

