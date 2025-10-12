/**
 * 大模型统一管理服务
 */
import { authService } from './auth.service';

// 统一的请求工具，正确处理认证token
const request = {
  getHeaders() {
    const token = authService.getToken();
    return {
      'Authorization': token ? `Bearer ${token}` : '',
      'Content-Type': 'application/json'
    };
  },

  async get(url: string) {
    const response = await fetch(url, {
      headers: this.getHeaders()
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  },
  
  async post(url: string, data?: any) {
    const response = await fetch(url, {
      method: 'POST',
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  },
  
  async put(url: string, data?: any) {
    const response = await fetch(url, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: data ? JSON.stringify(data) : undefined
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  },
  
  async delete(url: string) {
    const response = await fetch(url, {
      method: 'DELETE',
      headers: this.getHeaders()
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  }
};

// 类型定义
export interface ModelInfo {
  id: number;
  model_id: string;
  model_name: string;
  display_name?: string;
  model_type: 'local' | 'api' | 'download' | 'cloud';
  model_source?: string;
  model_family?: string;
  model_size?: string;
  parameter_count?: number;
  model_version?: string;
  model_path?: string;
  api_url?: string;
  api_provider?: string;
  status: 'available' | 'downloading' | 'error' | 'offline' | 'unknown';
  download_progress?: number;
  file_size?: number;
  disk_usage?: number;
  supported_context_length?: number;
  max_tokens?: number;
  inference_speed?: number;
  memory_usage?: number;
  capabilities?: string[];
  languages?: string[];
  tags?: string[];
  usage_count: number;
  last_used_at?: string;
  benchmark_scores?: Record<string, number>;
  quality_rating?: number;
  is_active: boolean;
  is_favorite: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
  last_scanned_at?: string;
  extra_metadata?: Record<string, any>;
}

export interface ModelOverview {
  total_models: number;
  type_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  recent_used: ModelInfo[];
  favorites: ModelInfo[];
  total_disk_usage: number;
  downloading_tasks: number;
}

export interface ModelListParams {
  page?: number;
  page_size?: number;
  model_type?: string;
  status?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ModelListResponse {
  total: number;
  page: number;
  page_size: number;
  models: ModelInfo[];
}

export interface ModelDetailResponse extends ModelInfo {
  usage_stats: {
    total_usage: number;
    usage_by_type: Record<string, number>;
    avg_latency?: number;
    avg_throughput?: number;
    total_input_tokens: number;
    total_output_tokens: number;
    recent_usage: Record<string, number>;
  };
  categories: Array<{
    id: number;
    name: string;
    display_name: string;
    description?: string;
    icon?: string;
    color?: string;
  }>;
}

export interface ModelUpdateRequest {
  display_name?: string;
  notes?: string;
  is_favorite?: boolean;
  tags?: string[];
  quality_rating?: number;
  capabilities?: string[];
  languages?: string[];
}

export interface LocalScanRequest {
  scan_paths: string[];
}

export interface LocalScanResponse {
  scanned_paths: string[];
  found_models: Array<{
    path: string;
    name: string;
    size: number;
    file_count: number;
    detected_info: Record<string, any>;
    last_modified: string;
  }>;
  errors: string[];
}

export interface ModelRegistrationRequest {
  registry_id: number;
  display_name?: string;
  notes?: string;
}

export interface UsageLogRequest {
  usage_type: string;
  task_name?: string;
  input_tokens?: number;
  output_tokens?: number;
  latency_ms?: number;
  throughput?: number;
  cost_estimate?: number;
  quality_score?: number;
  user_rating?: number;
  extra_data?: Record<string, any>;
}

export interface ModelCategory {
  id: number;
  name: string;
  display_name: string;
  description?: string;
  icon?: string;
  color?: string;
  sort_order: number;
  is_active: boolean;
}

class ModelManagementService {
  private baseURL = '/api/v1/model-management';

  /**
   * 获取模型总览统计
   */
  async getOverview(): Promise<ModelOverview> {
    return await request.get(`${this.baseURL}/overview`);
  }

  /**
   * 获取模型列表
   */
  async getModelsList(params: ModelListParams = {}): Promise<ModelListResponse> {
    const queryParams = new URLSearchParams();
    
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        queryParams.append(key, String(value));
      }
    });

    const url = `${this.baseURL}/list${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    return await request.get(url);
  }

  /**
   * 获取模型详细信息
   */
  async getModelDetail(modelId: number): Promise<ModelDetailResponse> {
    return await request.get(`${this.baseURL}/${modelId}`);
  }

  /**
   * 更新模型信息
   */
  async updateModel(modelId: number, updates: ModelUpdateRequest): Promise<{ success: boolean; message: string }> {
    return await request.put(`${this.baseURL}/${modelId}`, updates);
  }

  /**
   * 删除模型
   */
  async deleteModel(modelId: number): Promise<{ success: boolean; message: string }> {
    return await request.delete(`${this.baseURL}/${modelId}`);
  }

  /**
   * 扫描本地模型
   */
  async scanLocalModels(scanPaths: string[]): Promise<LocalScanResponse> {
    return await request.post(`${this.baseURL}/scan-local`, { scan_paths: scanPaths });
  }

  /**
   * 获取本地模型注册表
   */
  async getLocalRegistry(): Promise<{ registry_entries: any[] }> {
    return await request.get(`${this.baseURL}/local-registry/list`);
  }

  /**
   * 注册本地模型
   */
  async registerLocalModel(request: ModelRegistrationRequest): Promise<{ success: boolean; model_id: number; message: string }> {
    return await request.post(`${this.baseURL}/register-local`, request);
  }

  /**
   * 记录模型使用日志
   */
  async logModelUsage(modelId: number, usageData: UsageLogRequest): Promise<{ success: boolean; message: string }> {
    return await request.post(`${this.baseURL}/${modelId}/usage-log`, usageData);
  }

  /**
   * 获取模型分类列表
   */
  async getCategories(): Promise<{ categories: ModelCategory[] }> {
    return await request.get(`${this.baseURL}/categories/list`);
  }

  /**
   * 将模型添加到分类
   */
  async addModelToCategory(modelId: number, categoryId: number): Promise<{ success: boolean; message: string }> {
    return await request.post(`${this.baseURL}/${modelId}/category/${categoryId}`);
  }

  /**
   * 获取使用统计
   */
  async getUsageStatistics(days: number = 30): Promise<{
    total_usage: number;
    daily_usage: Record<string, number>;
    usage_by_model: Record<string, number>;
    usage_by_type: Record<string, number>;
  }> {
    return await request.get(`${this.baseURL}/stats/usage?days=${days}`);
  }

  /**
   * 获取性能统计
   */
  async getPerformanceStatistics(): Promise<{
    avg_latency: number;
    avg_throughput: number;
    performance_trends: Record<string, any>;
  }> {
    return await request.get(`${this.baseURL}/stats/performance`);
  }

  /**
   * 批量操作模型
   */
  async batchUpdateModels(
    modelIds: number[], 
    operation: 'favorite' | 'unfavorite' | 'delete' | 'activate' | 'deactivate',
    params?: Record<string, any>
  ): Promise<{ success: boolean; message: string; results: Array<{ model_id: number; success: boolean; error?: string }> }> {
    // 这里可以实现批量操作的逻辑
    const results = [];
    
    for (const modelId of modelIds) {
      try {
        switch (operation) {
          case 'favorite':
            await this.updateModel(modelId, { is_favorite: true });
            results.push({ model_id: modelId, success: true });
            break;
          case 'unfavorite':
            await this.updateModel(modelId, { is_favorite: false });
            results.push({ model_id: modelId, success: true });
            break;
          case 'delete':
            await this.deleteModel(modelId);
            results.push({ model_id: modelId, success: true });
            break;
          default:
            results.push({ model_id: modelId, success: false, error: '不支持的操作' });
        }
      } catch (error) {
        results.push({ 
          model_id: modelId, 
          success: false, 
          error: error instanceof Error ? error.message : '操作失败'
        });
      }
    }
    
    const successCount = results.filter(r => r.success).length;
    return {
      success: successCount === modelIds.length,
      message: `批量操作完成：成功 ${successCount}/${modelIds.length}`,
      results
    };
  }

  /**
   * 导出模型配置
   */
  async exportModelConfig(modelId: number): Promise<Blob> {
    const response = await fetch(`${this.baseURL}/${modelId}/export`, {
      headers: this.getHeaders()
    });
    
    if (!response.ok) {
      throw new Error('导出配置失败');
    }
    
    return await response.blob();
  }

  /**
   * 导入模型配置
   */
  async importModelConfig(file: File): Promise<{ success: boolean; message: string; model_id?: number }> {
    const formData = new FormData();
    formData.append('config_file', file);
    
    const response = await fetch(`${this.baseURL}/import`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${authService.getToken()}`
      },
      body: formData
    });
    
    if (!response.ok) {
      throw new Error('导入配置失败');
    }
    
    return await response.json();
  }

  /**
   * 测试模型连接
   */
  async testModelConnection(modelId: number): Promise<{
    success: boolean;
    latency?: number;
    error?: string;
    details?: Record<string, any>;
  }> {
    return await request.post(`${this.baseURL}/${modelId}/test-connection`);
  }

  /**
   * 获取模型使用报告
   */
  async getModelReport(
    modelId: number,
    reportType: 'usage' | 'performance' | 'comparison' = 'usage',
    timeRange: string = '30d'
  ): Promise<{
    report_data: Record<string, any>;
    generated_at: string;
    report_type: string;
  }> {
    return await request.get(`${this.baseURL}/${modelId}/report?type=${reportType}&range=${timeRange}`);
  }

  /**
   * 同步现有的模型配置
   */
  async syncExistingModels(): Promise<{
    success: boolean;
    message: string;
    details: {
      synced_user_configs: number;
      synced_model_configs: number;
      scanned_local_models: number;
    };
  }> {
    return await request.post(`${this.baseURL}/sync-existing`);
  }
}

// 创建单例实例
export const modelManagementService = new ModelManagementService();

// 导出类型和服务实例
export default modelManagementService;
