import { v4 as uuidv4 } from 'uuid';
import { authService } from '../services/auth.service';
import { UserConfigService } from '../services/userConfigService';
import { api } from './api';

// 配置类型定义
export interface BaseConfig {
  id: string;           // 配置的唯一标识
  name: string;         // 配置名称
  type: string;         // 配置类型（如 'openai', 'dify_chatflow' 等）
  userId: string;       // 用户ID
  createdAt: number;    // 创建时间
  updatedAt: number;    // 更新时间
}

export interface ModelConfig extends BaseConfig {
  baseUrl: string;
  apiKey: string;
  modelName: string;
  additionalParams?: Record<string, any>;
}

export interface RAGConfig extends BaseConfig {
  url: string;
  apiKey?: string;
  requestHeaders?: Record<string, any>;
  requestTemplate?: Record<string, any>;
  responsePath?: string;
  streamEventField?: string;
  streamEventValue?: string;
}

export interface MinerUConfig extends BaseConfig {
  baseUrl: string;
  apiKey: string;
  isActive?: boolean;
}

// 用户配置存储结构
interface UserConfigs {
  models: ModelConfig[];
  rags: RAGConfig[];
  mineru: MinerUConfig[];
}

export class ConfigManager {
  private static instance: ConfigManager;
  private readonly STORAGE_KEY = 'rag_eval_user_configs';
  private currentUserId: string | null = null;
  private userConfigService: UserConfigService;

  private constructor() {
    this.userConfigService = UserConfigService.getInstance();
    this.initializeUserId();
  }

  private async initializeUserId() {
    const userInfo = await authService.getCurrentUser();
    this.currentUserId = userInfo?.id || null;
  }

  public static getInstance(): ConfigManager {
    if (!ConfigManager.instance) {
      ConfigManager.instance = new ConfigManager();
    }
    return ConfigManager.instance;
  }

  // 更新当前用户ID
  public async updateCurrentUserId(): Promise<void> {
    const userInfo = await authService.getCurrentUser();
    this.currentUserId = userInfo?.id || null;
  }

  // 获取当前用户ID
  public getCurrentUserId(): string | null {
    return this.currentUserId;
  }

  // 获取用户所有配置
  private getUserConfigs(): UserConfigs {
    if (!this.currentUserId) {
      return { models: [], rags: [], mineru: [] };
    }
    const configs = localStorage.getItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
    return configs ? JSON.parse(configs) : { models: [], rags: [], mineru: [] };
  }

  // 保存用户所有配置
  private saveUserConfigs(configs: UserConfigs): void {
    if (!this.currentUserId) {
      console.warn('Attempting to save configs without user ID');
      return;
    }
    localStorage.setItem(`${this.STORAGE_KEY}_${this.currentUserId}`, JSON.stringify(configs));
  }

  // 创建新配置 - 直接使用服务端存储
  public async createConfig<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag' | 'mineru'): Promise<T> {
    const result = await this.createConfigOnServer(config, type);
    console.log('服务端配置创建成功:', result);
    return result;
  }

  private async createConfigOnServer<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag' | 'mineru'): Promise<T> {
    try {
      console.log('尝试在服务端创建配置:', { type, name: config.name });
      
      if (type === 'model') {
        const result = await this.userConfigService.createModelConfig(config as any);
        console.log('服务端创建模型配置成功:', result.id);
        return result as unknown as T;
      } else if (type === 'rag') {
        const result = await this.userConfigService.createRAGConfig(config as any);
        console.log('服务端创建RAG配置成功:', result.id);
        return result as unknown as T;
      } else if (type === 'mineru') {
        // MinerU配置使用后端API
        // 转换字段名以匹配后端schema
        const mineruConfig = config as any;
        const serverConfigData = {
          name: mineruConfig.name,
          base_url: mineruConfig.baseUrl, // 转换字段名
          api_key: mineruConfig.apiKey,   // 转换字段名
          is_active: mineruConfig.isActive || true
        };
        
        const response = await api.post<any>('/user-configs/mineru-configs', serverConfigData);
        console.log('服务端创建MinerU配置成功:', response);
        return response as unknown as T;
      }
    } catch (error: any) {
      console.error('服务端创建配置失败:', error);
      throw error;
    }
  }

  private async createConfigLocally<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag' | 'mineru'): Promise<T> {
    await this.updateCurrentUserId();
    const newConfig = {
      ...config,
      id: uuidv4(),
      userId: this.currentUserId,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    } as T;

    const userConfigs = this.getUserConfigs();
    if (type === 'model') {
      userConfigs.models.push(newConfig as unknown as ModelConfig);
    } else if (type === 'rag') {
      userConfigs.rags.push(newConfig as unknown as RAGConfig);
    } else if (type === 'mineru') {
      userConfigs.mineru.push(newConfig as unknown as MinerUConfig);
    }
    this.saveUserConfigs(userConfigs);
    return newConfig;
  }

  // 更新配置
  public async updateConfig<T extends ModelConfig | RAGConfig | MinerUConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    return await this.updateConfigOnServer(configId, updates, type);
  }

  private async updateConfigOnServer<T extends ModelConfig | RAGConfig | MinerUConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    if (type === 'model') {
      const result = await this.userConfigService.updateModelConfig(configId, updates as Partial<ModelConfig>);
      return result as T | null;
    } else if (type === 'rag') {
      const result = await this.userConfigService.updateRAGConfig(configId, updates as Partial<RAGConfig>);
      return result as T | null;
    } else if (type === 'mineru') {
      // MinerU配置使用后端API
      // 转换字段名以匹配后端schema
      const mineruUpdates = updates as any;
      const serverUpdateData: any = {};
      if (mineruUpdates.name !== undefined) serverUpdateData.name = mineruUpdates.name;
      if (mineruUpdates.baseUrl !== undefined) serverUpdateData.base_url = mineruUpdates.baseUrl;
      if (mineruUpdates.apiKey !== undefined) serverUpdateData.api_key = mineruUpdates.apiKey;
      if (mineruUpdates.isActive !== undefined) serverUpdateData.is_active = mineruUpdates.isActive;
      
      const response = await api.put<any>(`/user-configs/mineru-configs/${configId}`, serverUpdateData);
      console.log('服务端更新MinerU配置成功:', response);
      return response as unknown as T | null;
    }
  }

  private async updateConfigLocally<T extends ModelConfig | RAGConfig | MinerUConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : type === 'rag' ? userConfigs.rags : userConfigs.mineru;
    const index = configs.findIndex(c => c.id === configId);
    
    if (index === -1) return null;
    
    // 验证配置是否属于当前用户
    if (configs[index].userId !== this.currentUserId) {
      return null;
    }
    
    // 移除不应该被更新的字段
    const { id, userId, createdAt, ...safeUpdates } = updates as any;
    
    const updatedConfig = {
      ...configs[index],
      ...safeUpdates,
      updatedAt: Date.now(),
    } as T;

    configs[index] = updatedConfig;
    this.saveUserConfigs(userConfigs);
    return updatedConfig;
  }

  // 删除配置
  public async deleteConfig(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<boolean> {
    return await this.deleteConfigOnServer(configId, type);
  }

  private async deleteConfigOnServer(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<boolean> {
    if (type === 'model') {
      return await this.userConfigService.deleteModelConfig(configId);
    } else if (type === 'rag') {
      return await this.userConfigService.deleteRAGConfig(configId);
    } else if (type === 'mineru') {
      // MinerU配置使用后端API
      await api.delete(`/user-configs/mineru-configs/${configId}`);
      console.log('服务端删除MinerU配置成功');
      return true;
    }
  }

  private async deleteConfigLocally(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<boolean> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : type === 'rag' ? userConfigs.rags : userConfigs.mineru;
    const index = configs.findIndex(c => c.id === configId);
    
    if (index === -1) return false;

    configs.splice(index, 1);
    this.saveUserConfigs(userConfigs);
    return true;
  }

  // 获取配置
  public async getConfig<T extends BaseConfig>(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    return await this.getConfigFromServer(configId, type);
  }

  private async getConfigFromServer<T extends BaseConfig>(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    if (type === 'model') {
      const result = await this.userConfigService.getModelConfig(configId);
      return result as unknown as T | null;
    } else if (type === 'rag') {
      const result = await this.userConfigService.getRAGConfig(configId);
      return result as unknown as T | null;
    } else if (type === 'mineru') {
      // MinerU配置暂时使用本地存储
      return this.getConfigLocally(configId, type);
    }
  }

  private async getConfigLocally<T extends BaseConfig>(configId: string, type: 'model' | 'rag' | 'mineru'): Promise<T | null> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : type === 'rag' ? userConfigs.rags : userConfigs.mineru;
    return configs.find(c => c.id === configId) as unknown as T || null;
  }

  // 获取所有配置
  public async getAllConfigs<T extends BaseConfig>(type: 'model' | 'rag' | 'mineru'): Promise<T[]> {
    try {
      const serverConfigs = await this.getAllConfigsFromServer<T>(type);
      console.log(`✅ 从服务端获取${type}配置成功:`, serverConfigs.length, '个');
      return serverConfigs;
    } catch (error) {
      console.error(`❌ 服务端获取${type}配置失败:`, error);
      return [];
    }
  }

  private async getAllConfigsFromServer<T extends BaseConfig>(type: 'model' | 'rag' | 'mineru'): Promise<T[]> {
    if (type === 'model') {
      const result = await this.userConfigService.getModelConfigs();
      return result as unknown as T[];
    } else if (type === 'rag') {
      const result = await this.userConfigService.getRAGConfigs();
      return result as unknown as T[];
    } else if (type === 'mineru') {
      // MinerU配置使用后端API
      const response = await api.get<any[]>('/user-configs/mineru-configs');
      console.log('服务端获取MinerU配置成功:', response);
      
      // 转换字段名以匹配前端接口
      const convertedResponse = response.map((config: any) => ({
        ...config,
        baseUrl: config.base_url, // 转换字段名
        apiKey: config.api_key,   // 转换字段名
        isActive: config.is_active
      }));
      
      return convertedResponse as unknown as T[];
    }
  }



  // 根据名称和类型查找配置
  public async findConfigByNameAndType(name: string, type: string, configType: 'model' | 'rag' | 'mineru'): Promise<BaseConfig | null> {
    if (configType === 'mineru') {
      // MinerU配置暂时使用本地存储
      return this.findConfigByNameAndTypeLocally(name, type, configType);
    }
    return await this.userConfigService.findConfigByNameAndType(name, type, configType as 'model' | 'rag');
  }

  private findConfigByNameAndTypeLocally(name: string, type: string, configType: 'model' | 'rag' | 'mineru'): BaseConfig | null {
    const userConfigs = this.getUserConfigs();
    const configs = configType === 'model' ? userConfigs.models : configType === 'rag' ? userConfigs.rags : userConfigs.mineru;
    return configs.find(c => c.name === name && c.type === type) || null;
  }

  // 清除当前用户所有配置
  public async clearUserConfigs(): Promise<void> {
    if (!this.currentUserId) return;
    
    // 清理服务端配置
    try {
      const result = await this.userConfigService.clearAllConfigs();
      console.log('服务端配置清理成功:', result);
      
      // 服务端清理成功后，也清理本地存储
      localStorage.removeItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
      console.log('本地配置也已清理');
      return;
    } catch (error) {
      console.warn('服务端清理失败:', error);
    }
    
    // 清理本地存储
    localStorage.removeItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
    console.log('本地配置已清理');
  }

  // 根据类型和名称查找RAG配置
  public async findRAGConfigByTypeAndName(type: string, name: string): Promise<RAGConfig | null> {
    return await this.userConfigService.findRAGConfigByTypeAndName(type, name);
  }

  // ==================== 数据迁移和同步方法 ====================

  // 检查本地是否有配置需要迁移
  public hasLocalConfigs(): boolean {
    if (!this.currentUserId) return false;
    const configs = this.getUserConfigs();
    return configs.models.length > 0 || configs.rags.length > 0 || configs.mineru.length > 0;
  }

  // 同步本地配置到服务端
  public async syncLocalConfigsToServer(): Promise<{ success: number; failed: number; errors: string[] }> {
    const result = { success: 0, failed: 0, errors: [] as string[] };
    
    const localConfigs = this.getUserConfigs();
    
    // 同步模型配置
    for (const config of localConfigs.models) {
      try {
        // 先检查是否已存在同名配置
        const existingConfig = await this.userConfigService.findConfigByNameAndType(config.name, config.type, 'model');
        
        if (existingConfig) {
          // 如果存在，更新配置
          await this.userConfigService.updateModelConfig(existingConfig.id, config);
          console.log('模型配置更新成功:', config.name);
        } else {
          // 如果不存在，创建新配置
          await this.userConfigService.createModelConfig(config);
          console.log('模型配置创建成功:', config.name);
        }
        result.success++;
      } catch (error) {
        result.failed++;
        const errorMsg = `同步模型配置失败 [${config.name}]: ${error instanceof Error ? error.message : String(error)}`;
        result.errors.push(errorMsg);
        console.error('同步模型配置详细错误:', error);
      }
    }
    
    // 同步RAG配置
    for (const config of localConfigs.rags) {
      try {
        // 先检查是否已存在同名配置
        const existingConfig = await this.userConfigService.findConfigByNameAndType(config.name, config.type, 'rag');
        
        if (existingConfig) {
          // 如果存在，更新配置
          await this.userConfigService.updateRAGConfig(existingConfig.id, config);
          console.log('RAG配置更新成功:', config.name);
        } else {
          // 如果不存在，创建新配置
          await this.userConfigService.createRAGConfig(config);
          console.log('RAG配置创建成功:', config.name);
        }
        result.success++;
      } catch (error) {
        result.failed++;
        const errorMsg = `同步RAG配置失败 [${config.name}]: ${error instanceof Error ? error.message : String(error)}`;
        result.errors.push(errorMsg);
        console.error('同步RAG配置详细错误:', error);
      }
    }
    
    // 只有在完全成功时才清理本地存储
    if (result.failed === 0 && result.success > 0) {
      this.clearUserConfigs();
      console.log('本地配置已清理');
    } else if (result.failed > 0) {
      console.warn(`迁移未完全成功，保留本地配置。成功: ${result.success}, 失败: ${result.failed}`);
    }
    
    return result;
  }


  // 导出所有配置（用于备份）
  public async exportAllConfigs(): Promise<{ models: ModelConfig[]; rags: RAGConfig[]; mineru: MinerUConfig[] }> {
    const [models, rags, mineru] = await Promise.all([
      this.getAllConfigs<ModelConfig>('model'),
      this.getAllConfigs<RAGConfig>('rag'),
      this.getAllConfigs<MinerUConfig>('mineru')
    ]);
    
    return { models, rags, mineru };
  }

  // 导入配置（从备份文件恢复）
  public async importConfigs(configData: { models: ModelConfig[]; rags: RAGConfig[]; mineru?: MinerUConfig[] }): Promise<{ success: number; failed: number; errors: string[] }> {
    const result = { success: 0, failed: 0, errors: [] as string[] };
    
    try {
      // 导入模型配置
      for (const model of configData.models) {
        try {
          // 移除id字段，让系统生成新的id
          const { id, ...modelWithoutId } = model;
          await this.createConfig(modelWithoutId, 'model');
          result.success++;
        } catch (error) {
          result.failed++;
          result.errors.push(`模型配置 "${model.name}" 导入失败: ${error}`);
        }
      }
      
      // 导入RAG配置
      for (const rag of configData.rags) {
        try {
          // 移除id字段，让系统生成新的id
          const { id, ...ragWithoutId } = rag;
          await this.createConfig(ragWithoutId, 'rag');
          result.success++;
        } catch (error) {
          result.failed++;
          result.errors.push(`RAG配置 "${rag.name}" 导入失败: ${error}`);
        }
      }
      
      // 导入MinerU配置
      if (configData.mineru) {
        for (const mineru of configData.mineru) {
          try {
            // 移除id字段，让系统生成新的id
            const { id, ...mineruWithoutId } = mineru;
            await this.createConfig(mineruWithoutId, 'mineru');
            result.success++;
          } catch (error) {
            result.failed++;
            result.errors.push(`MinerU配置 "${mineru.name}" 导入失败: ${error}`);
          }
        }
      }
      
      // 触发配置变化事件，通知页面刷新
      if (result.success > 0) {
        window.dispatchEvent(new CustomEvent('configChanged'));
      }
      
      return result;
    } catch (error) {
      throw new Error(`导入配置失败: ${error}`);
    }
  }

  // 调试：获取详细状态信息
  public async getDetailedStatus(): Promise<{
    storageMode: 'server' | 'local';
    userInfo: any;
    localConfigs: { models: number; rags: number; mineru: number };
    serverConfigs: { models: number; rags: number; mineru: number; error?: string };
  }> {
    const status = {
      storageMode: 'server' as 'server' | 'local',
      userInfo: null as any,
      localConfigs: { models: 0, rags: 0, mineru: 0 },
      serverConfigs: { models: 0, rags: 0, mineru: 0, error: undefined as string | undefined }
    };

    // 获取用户信息
    try {
      await this.updateCurrentUserId();
      status.userInfo = { id: this.currentUserId };
    } catch (error) {
      status.userInfo = { error: error?.toString() };
    }

    // 获取本地配置数量
    try {
      const localUserConfigs = this.getUserConfigs();
      status.localConfigs.models = localUserConfigs.models.length;
      status.localConfigs.rags = localUserConfigs.rags.length;
      status.localConfigs.mineru = localUserConfigs.mineru.length;
    } catch (error) {
      console.error('获取本地配置失败:', error);
    }

    // 获取服务端配置数量
    try {
      const serverModels = await this.userConfigService.getModelConfigs();
      const serverRags = await this.userConfigService.getRAGConfigs();
      status.serverConfigs.models = serverModels.length;
      status.serverConfigs.rags = serverRags.length;
      status.serverConfigs.mineru = 0; // MinerU配置暂时使用本地存储
    } catch (error) {
      status.serverConfigs.error = error?.toString();
      console.error('获取服务端配置失败:', error);
    }

    return status;
  }
}
