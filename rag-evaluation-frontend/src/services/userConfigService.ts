import { api } from '../utils/api';
import { ModelConfig, RAGConfig } from '../utils/configManager';

// 与后端API对应的接口定义
export interface UserModelConfigCreate {
  name: string;
  type: string;
  base_url: string;
  api_key?: string;
  model_name: string;
  additional_params?: Record<string, any>;
  is_active?: boolean;
}

export interface UserModelConfigOut extends UserModelConfigCreate {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface UserRAGConfigCreate {
  name: string;
  type: string;
  url: string;
  api_key?: string;
  request_headers?: Record<string, any>;
  request_template?: Record<string, any>;
  response_path?: string;
  stream_event_field?: string;
  stream_event_value?: string;
  is_active?: boolean;
}

export interface UserRAGConfigOut extends UserRAGConfigCreate {
  id: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

// 转换函数：前端配置 -> 后端格式
function convertModelConfigToServerFormat(config: Omit<ModelConfig, 'id' | 'userId' | 'createdAt' | 'updatedAt'>): UserModelConfigCreate {
  let additionalParams = {};
  
  // 处理 additionalParams，可能是字符串或对象
  if (config.additionalParams) {
    if (typeof config.additionalParams === 'string') {
      try {
        additionalParams = JSON.parse(config.additionalParams);
      } catch (error) {
        console.warn('无法解析 additionalParams JSON字符串:', config.additionalParams, error);
        additionalParams = {};
      }
    } else {
      additionalParams = config.additionalParams;
    }
  }
  
  return {
    name: config.name,
    type: config.type,
    base_url: config.baseUrl,
    api_key: config.apiKey,
    model_name: config.modelName,
    additional_params: additionalParams,
    is_active: true
  };
}

function convertRAGConfigToServerFormat(config: Omit<RAGConfig, 'id' | 'userId' | 'createdAt' | 'updatedAt'>): UserRAGConfigCreate {
  // 安全解析 requestHeaders
  let requestHeaders = {};
  if (config.requestHeaders) {
    if (typeof config.requestHeaders === 'string') {
      try {
        requestHeaders = JSON.parse(config.requestHeaders);
      } catch (error) {
        console.warn('无法解析 requestHeaders JSON字符串:', config.requestHeaders, error);
        requestHeaders = {};
      }
    } else {
      requestHeaders = config.requestHeaders;
    }
  }

  // 安全解析 requestTemplate
  let requestTemplate = {};
  if (config.requestTemplate) {
    if (typeof config.requestTemplate === 'string') {
      try {
        requestTemplate = JSON.parse(config.requestTemplate);
      } catch (error) {
        console.warn('无法解析 requestTemplate JSON字符串:', config.requestTemplate, error);
        requestTemplate = {};
      }
    } else {
      requestTemplate = config.requestTemplate;
    }
  }

  return {
    name: config.name,
    type: config.type,
    url: config.url,
    api_key: config.apiKey,
    request_headers: requestHeaders,
    request_template: requestTemplate,
    response_path: config.responsePath,
    stream_event_field: config.streamEventField,
    stream_event_value: config.streamEventValue,
    is_active: true
  };
}

// 转换函数：后端格式 -> 前端配置
function convertServerModelConfigToFrontend(serverConfig: UserModelConfigOut): ModelConfig {
  return {
    id: serverConfig.id,
    name: serverConfig.name,
    type: serverConfig.type,
    baseUrl: serverConfig.base_url,
    apiKey: serverConfig.api_key || '',
    modelName: serverConfig.model_name,
    additionalParams: serverConfig.additional_params || {},
    userId: serverConfig.user_id,
    createdAt: new Date(serverConfig.created_at).getTime(),
    updatedAt: new Date(serverConfig.updated_at).getTime()
  };
}

function convertServerRAGConfigToFrontend(serverConfig: UserRAGConfigOut): RAGConfig {
  return {
    id: serverConfig.id,
    name: serverConfig.name,
    type: serverConfig.type,
    url: serverConfig.url,
    apiKey: serverConfig.api_key,
    requestHeaders: serverConfig.request_headers || {},
    requestTemplate: serverConfig.request_template || {},
    responsePath: serverConfig.response_path,
    streamEventField: serverConfig.stream_event_field,
    streamEventValue: serverConfig.stream_event_value,
    userId: serverConfig.user_id,
    createdAt: new Date(serverConfig.created_at).getTime(),
    updatedAt: new Date(serverConfig.updated_at).getTime()
  };
}

export class UserConfigService {
  private static instance: UserConfigService;

  public static getInstance(): UserConfigService {
    if (!UserConfigService.instance) {
      UserConfigService.instance = new UserConfigService();
    }
    return UserConfigService.instance;
  }

  // ==================== 模型配置管理 ====================

  async createModelConfig(config: Omit<ModelConfig, 'id' | 'userId' | 'createdAt' | 'updatedAt'>): Promise<ModelConfig> {
    try {
      console.log('创建模型配置 - 原始数据:', config);
      const serverConfig = convertModelConfigToServerFormat(config);
      console.log('创建模型配置 - 转换后数据:', serverConfig);
      
      const response = await api.post<UserModelConfigOut>('/user-configs/model-configs', serverConfig);
      console.log('创建模型配置 - 服务端响应:', response);
      
      return convertServerModelConfigToFrontend(response);
    } catch (error) {
      console.error('创建模型配置失败:', error);
      throw error;
    }
  }

  async getModelConfigs(): Promise<ModelConfig[]> {
    const response = await api.get<UserModelConfigOut[]>('/user-configs/model-configs');
    return response.map(convertServerModelConfigToFrontend);
  }

  async getModelConfig(configId: string): Promise<ModelConfig | null> {
    try {
      const response = await api.get<UserModelConfigOut>(`/user-configs/model-configs/${configId}`);
      return convertServerModelConfigToFrontend(response);
    } catch (error) {
      console.error('获取模型配置失败:', error);
      return null;
    }
  }

  async updateModelConfig(configId: string, updates: Partial<ModelConfig>): Promise<ModelConfig | null> {
    try {
      // 转换更新数据格式
      const serverUpdates: any = {};
      if (updates.name !== undefined) serverUpdates.name = updates.name;
      if (updates.type !== undefined) serverUpdates.type = updates.type;
      if (updates.baseUrl !== undefined) serverUpdates.base_url = updates.baseUrl;
      if (updates.apiKey !== undefined) serverUpdates.api_key = updates.apiKey;
      if (updates.modelName !== undefined) serverUpdates.model_name = updates.modelName;
      if (updates.additionalParams !== undefined) {
        let additionalParams = {};
        if (typeof updates.additionalParams === 'string') {
          try {
            additionalParams = JSON.parse(updates.additionalParams);
          } catch (error) {
            console.warn('无法解析更新的 additionalParams JSON字符串:', updates.additionalParams, error);
            additionalParams = {};
          }
        } else {
          additionalParams = updates.additionalParams;
        }
        serverUpdates.additional_params = additionalParams;
      }

      const response = await api.put<UserModelConfigOut>(`/user-configs/model-configs/${configId}`, serverUpdates);
      return convertServerModelConfigToFrontend(response);
    } catch (error) {
      console.error('更新模型配置失败:', error);
      return null;
    }
  }

  async deleteModelConfig(configId: string): Promise<boolean> {
    try {
      await api.delete(`/user-configs/model-configs/${configId}`);
      return true;
    } catch (error) {
      console.error('删除模型配置失败:', error);
      return false;
    }
  }

  // ==================== RAG配置管理 ====================

  async createRAGConfig(config: Omit<RAGConfig, 'id' | 'userId' | 'createdAt' | 'updatedAt'>): Promise<RAGConfig> {
    const serverConfig = convertRAGConfigToServerFormat(config);
    const response = await api.post<UserRAGConfigOut>('/user-configs/rag-configs', serverConfig);
    return convertServerRAGConfigToFrontend(response);
  }

  async getRAGConfigs(): Promise<RAGConfig[]> {
    const response = await api.get<UserRAGConfigOut[]>('/user-configs/rag-configs');
    return response.map(convertServerRAGConfigToFrontend);
  }

  async getRAGConfig(configId: string): Promise<RAGConfig | null> {
    try {
      const response = await api.get<UserRAGConfigOut>(`/user-configs/rag-configs/${configId}`);
      return convertServerRAGConfigToFrontend(response);
    } catch (error) {
      console.error('获取RAG配置失败:', error);
      return null;
    }
  }

  async updateRAGConfig(configId: string, updates: Partial<RAGConfig>): Promise<RAGConfig | null> {
    try {
      // 转换更新数据格式
      const serverUpdates: any = {};
      if (updates.name !== undefined) serverUpdates.name = updates.name;
      if (updates.type !== undefined) serverUpdates.type = updates.type;
      if (updates.url !== undefined) serverUpdates.url = updates.url;
      if (updates.apiKey !== undefined) serverUpdates.api_key = updates.apiKey;
      if (updates.requestHeaders !== undefined) {
        // 处理 requestHeaders，确保发送对象格式
        if (typeof updates.requestHeaders === 'string') {
          try {
            serverUpdates.request_headers = JSON.parse(updates.requestHeaders);
          } catch (error) {
            console.warn('无法解析 requestHeaders JSON字符串:', updates.requestHeaders, error);
            serverUpdates.request_headers = {};
          }
        } else {
          serverUpdates.request_headers = updates.requestHeaders;
        }
      }
      if (updates.requestTemplate !== undefined) {
        // 处理 requestTemplate，确保发送对象格式
        if (typeof updates.requestTemplate === 'string') {
          try {
            serverUpdates.request_template = JSON.parse(updates.requestTemplate);
          } catch (error) {
            console.warn('无法解析 requestTemplate JSON字符串:', updates.requestTemplate, error);
            serverUpdates.request_template = {};
          }
        } else {
          serverUpdates.request_template = updates.requestTemplate;
        }
      }
      if (updates.responsePath !== undefined) serverUpdates.response_path = updates.responsePath;
      if (updates.streamEventField !== undefined) serverUpdates.stream_event_field = updates.streamEventField;
      if (updates.streamEventValue !== undefined) serverUpdates.stream_event_value = updates.streamEventValue;

      const response = await api.put<UserRAGConfigOut>(`/user-configs/rag-configs/${configId}`, serverUpdates);
      return convertServerRAGConfigToFrontend(response);
    } catch (error) {
      console.error('更新RAG配置失败:', error);
      return null;
    }
  }

  async deleteRAGConfig(configId: string): Promise<boolean> {
    try {
      await api.delete(`/user-configs/rag-configs/${configId}`);
      return true;
    } catch (error) {
      console.error('删除RAG配置失败:', error);
      return false;
    }
  }

  // ==================== 配置查找 ====================

  async findConfigByNameAndType(name: string, type: string, configType: 'model' | 'rag'): Promise<ModelConfig | RAGConfig | null> {
    try {
      const response = await api.get('/user-configs/configs/search', {
        params: { name, type, config_type: configType }
      });

      if (configType === 'model' && response.model_configs?.length > 0) {
        return convertServerModelConfigToFrontend(response.model_configs[0]);
      }
      
      if (configType === 'rag' && response.rag_configs?.length > 0) {
        return convertServerRAGConfigToFrontend(response.rag_configs[0]);
      }

      return null;
    } catch (error) {
      console.error('查找配置失败:', error);
      return null;
    }
  }

  async findRAGConfigByTypeAndName(type: string, name: string): Promise<RAGConfig | null> {
    return this.findConfigByNameAndType(name, type, 'rag') as Promise<RAGConfig | null>;
  }

  // ==================== 批量操作 ====================

  async clearAllConfigs(): Promise<{ message: string; deleted_model_configs: number; deleted_rag_configs: number }> {
    try {
      const response = await api.delete('/user-configs/configs/clear-all');
      return response;
    } catch (error) {
      console.error('清除所有配置失败:', error);
      throw error;
    }
  }
}
