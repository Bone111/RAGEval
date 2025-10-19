import { v4 as uuidv4 } from 'uuid';
import { authService } from '../services/auth.service';
import { UserConfigService } from '../services/userConfigService';

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

// 用户配置存储结构
interface UserConfigs {
  models: ModelConfig[];
  rags: RAGConfig[];
}

export class ConfigManager {
  private static instance: ConfigManager;
  private readonly STORAGE_KEY = 'rag_eval_user_configs';
  private currentUserId: string | null = null;
  private useServerStorage = true; // 默认使用服务端存储
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
      return { models: [], rags: [] };
    }
    const configs = localStorage.getItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
    return configs ? JSON.parse(configs) : { models: [], rags: [] };
  }

  // 保存用户所有配置
  private saveUserConfigs(configs: UserConfigs): void {
    if (!this.currentUserId) {
      console.warn('Attempting to save configs without user ID');
      return;
    }
    localStorage.setItem(`${this.STORAGE_KEY}_${this.currentUserId}`, JSON.stringify(configs));
  }

  // 创建新配置 - 优先使用服务端存储
  public async createConfig<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag'): Promise<T> {
    if (this.useServerStorage) {
      try {
        const result = await this.createConfigOnServer(config, type);
        console.log('服务端配置创建成功:', result);
        return result;
      } catch (error) {
        console.warn('服务端存储失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    // 本地存储逻辑（保持原有代码作为降级方案）
    return this.createConfigLocally(config, type);
  }

  private async createConfigOnServer<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag'): Promise<T> {
    try {
      console.log('尝试在服务端创建配置:', { type, name: config.name });
      
      if (type === 'model') {
        const result = await this.userConfigService.createModelConfig(config as any);
        console.log('服务端创建模型配置成功:', result.id);
        return result as unknown as T;
      } else {
        const result = await this.userConfigService.createRAGConfig(config as any);
        console.log('服务端创建RAG配置成功:', result.id);
        return result as unknown as T;
      }
    } catch (error) {
      console.error('服务端创建配置失败:', error);
      throw error;
    }
  }

  private async createConfigLocally<T extends BaseConfig>(config: Omit<T, 'id' | 'userId' | 'createdAt' | 'updatedAt'>, type: 'model' | 'rag'): Promise<T> {
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
    } else {
      userConfigs.rags.push(newConfig as unknown as RAGConfig);
    }
    this.saveUserConfigs(userConfigs);
    return newConfig;
  }

  // 更新配置
  public async updateConfig<T extends ModelConfig | RAGConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag'): Promise<T | null> {
    if (this.useServerStorage) {
      try {
        return await this.updateConfigOnServer(configId, updates, type);
      } catch (error) {
        console.warn('服务端更新失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    return this.updateConfigLocally(configId, updates, type);
  }

  private async updateConfigOnServer<T extends ModelConfig | RAGConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag'): Promise<T | null> {
    if (type === 'model') {
      const result = await this.userConfigService.updateModelConfig(configId, updates as Partial<ModelConfig>);
      return result as T | null;
    } else {
      const result = await this.userConfigService.updateRAGConfig(configId, updates as Partial<RAGConfig>);
      return result as T | null;
    }
  }

  private async updateConfigLocally<T extends ModelConfig | RAGConfig>(configId: string, updates: Partial<T>, type: 'model' | 'rag'): Promise<T | null> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : userConfigs.rags;
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
  public async deleteConfig(configId: string, type: 'model' | 'rag'): Promise<boolean> {
    if (this.useServerStorage) {
      try {
        return await this.deleteConfigOnServer(configId, type);
      } catch (error) {
        console.warn('服务端删除失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    return this.deleteConfigLocally(configId, type);
  }

  private async deleteConfigOnServer(configId: string, type: 'model' | 'rag'): Promise<boolean> {
    if (type === 'model') {
      return await this.userConfigService.deleteModelConfig(configId);
    } else {
      return await this.userConfigService.deleteRAGConfig(configId);
    }
  }

  private async deleteConfigLocally(configId: string, type: 'model' | 'rag'): Promise<boolean> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : userConfigs.rags;
    const index = configs.findIndex(c => c.id === configId);
    
    if (index === -1) return false;

    configs.splice(index, 1);
    this.saveUserConfigs(userConfigs);
    return true;
  }

  // 获取配置
  public async getConfig<T extends BaseConfig>(configId: string, type: 'model' | 'rag'): Promise<T | null> {
    if (this.useServerStorage) {
      try {
        return await this.getConfigFromServer(configId, type);
      } catch (error) {
        console.warn('服务端获取失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    return this.getConfigLocally(configId, type);
  }

  private async getConfigFromServer<T extends BaseConfig>(configId: string, type: 'model' | 'rag'): Promise<T | null> {
    if (type === 'model') {
      const result = await this.userConfigService.getModelConfig(configId);
      return result as unknown as T | null;
    } else {
      const result = await this.userConfigService.getRAGConfig(configId);
      return result as unknown as T | null;
    }
  }

  private async getConfigLocally<T extends BaseConfig>(configId: string, type: 'model' | 'rag'): Promise<T | null> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = type === 'model' ? userConfigs.models : userConfigs.rags;
    return configs.find(c => c.id === configId) as unknown as T || null;
  }

  // 获取所有配置
  public async getAllConfigs<T extends BaseConfig>(type: 'model' | 'rag'): Promise<T[]> {
    if (this.useServerStorage) {
      try {
        const serverConfigs = await this.getAllConfigsFromServer<T>(type);

        // 如果服务端返回空列表，但本地存在配置，说明之前的同步可能失败，优先展示本地数据
        if (serverConfigs.length === 0) {
          const localConfigs = await this.getAllConfigsLocally<T>(type);
          if (localConfigs.length > 0) {
            console.warn(`服务端${type}配置为空，使用本地配置作为降级数据`);
            return localConfigs;
          }
        }

        console.log(`✅ 从服务端获取${type}配置成功:`, serverConfigs.length, '个');
        return serverConfigs;
      } catch (error) {
        console.warn(`❌ 服务端获取${type}配置失败，降级到本地存储:`, error);
        // 暂时降级，但不永久关闭服务端存储
        const localConfigs = await this.getAllConfigsLocally<T>(type);
        console.log(`📂 使用本地${type}配置:`, localConfigs.length, '个');
        return localConfigs;
      }
    }
    
    return this.getAllConfigsLocally(type);
  }

  private async getAllConfigsFromServer<T extends BaseConfig>(type: 'model' | 'rag'): Promise<T[]> {
    if (type === 'model') {
      const result = await this.userConfigService.getModelConfigs();
      return result as unknown as T[];
    } else {
      const result = await this.userConfigService.getRAGConfigs();
      return result as unknown as T[];
    }
  }

  private async getAllConfigsLocally<T extends BaseConfig>(type: 'model' | 'rag'): Promise<T[]> {
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    return (type === 'model' ? userConfigs.models : userConfigs.rags) as unknown as T[];
  }

  // 根据名称和类型查找配置
  public async findConfigByNameAndType(name: string, type: string, configType: 'model' | 'rag'): Promise<BaseConfig | null> {
    if (this.useServerStorage) {
      try {
        return await this.userConfigService.findConfigByNameAndType(name, type, configType);
      } catch (error) {
        console.warn('服务端查找失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    const configs = configType === 'model' ? userConfigs.models : userConfigs.rags;
    return configs.find(c => c.name === name && c.type === type) || null;
  }

  // 清除当前用户所有配置
  public async clearUserConfigs(): Promise<void> {
    if (!this.currentUserId) return;
    
    // 优先尝试清理服务端配置
    if (this.useServerStorage) {
      try {
        const result = await this.userConfigService.clearAllConfigs();
        console.log('服务端配置清理成功:', result);
        
        // 服务端清理成功后，也清理本地存储
        localStorage.removeItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
        console.log('本地配置也已清理');
        return;
      } catch (error) {
        console.warn('服务端清理失败，降级到本地清理:', error);
        // 服务端清理失败时，仍然清理本地存储
      }
    }
    
    // 清理本地存储（降级方案或本地存储模式）
    localStorage.removeItem(`${this.STORAGE_KEY}_${this.currentUserId}`);
    console.log('本地配置已清理');
  }

  // 根据类型和名称查找RAG配置
  public async findRAGConfigByTypeAndName(type: string, name: string): Promise<RAGConfig | null> {
    if (this.useServerStorage) {
      try {
        return await this.userConfigService.findRAGConfigByTypeAndName(type, name);
      } catch (error) {
        console.warn('服务端查找RAG配置失败，降级到本地存储:', error);
        this.useServerStorage = false;
      }
    }
    
    await this.updateCurrentUserId();
    const userConfigs = this.getUserConfigs();
    return userConfigs.rags.find(c => c.type === type && c.name === name) || null;
  }

  // ==================== 数据迁移和同步方法 ====================

  // 检查本地是否有配置需要迁移
  public hasLocalConfigs(): boolean {
    if (!this.currentUserId) return false;
    const configs = this.getUserConfigs();
    return configs.models.length > 0 || configs.rags.length > 0;
  }

  // 同步本地配置到服务端
  public async syncLocalConfigsToServer(): Promise<{ success: number; failed: number; errors: string[] }> {
    const result = { success: 0, failed: 0, errors: [] as string[] };
    
    if (!this.useServerStorage) {
      result.errors.push('服务端存储不可用');
      return result;
    }
    
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

  // 强制使用本地存储
  public forceUseLocalStorage(): void {
    this.useServerStorage = false;
    console.log('已切换到本地存储模式');
  }

  // 重新尝试使用服务端存储
  public enableServerStorage(): void {
    this.useServerStorage = true;
    console.log('已重新启用服务端存储');
  }

  // 获取当前存储模式
  public getCurrentStorageMode(): 'server' | 'local' {
    return this.useServerStorage ? 'server' : 'local';
  }

  // 导出所有配置（用于备份）
  public async exportAllConfigs(): Promise<{ models: ModelConfig[]; rags: RAGConfig[] }> {
    const [models, rags] = await Promise.all([
      this.getAllConfigs<ModelConfig>('model'),
      this.getAllConfigs<RAGConfig>('rag')
    ]);
    
    return { models, rags };
  }

  // 导入配置（从备份文件恢复）
  public async importConfigs(configData: { models: ModelConfig[]; rags: RAGConfig[] }): Promise<{ success: number; failed: number; errors: string[] }> {
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
    localConfigs: { models: number; rags: number };
    serverConfigs: { models: number; rags: number; error?: string };
  }> {
    const status = {
      storageMode: this.getCurrentStorageMode(),
      userInfo: null as any,
      localConfigs: { models: 0, rags: 0 },
      serverConfigs: { models: 0, rags: 0, error: undefined as string | undefined }
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
    } catch (error) {
      console.error('获取本地配置失败:', error);
    }

    // 获取服务端配置数量
    try {
      const serverModels = await this.userConfigService.getModelConfigs();
      const serverRags = await this.userConfigService.getRAGConfigs();
      status.serverConfigs.models = serverModels.length;
      status.serverConfigs.rags = serverRags.length;
    } catch (error) {
      status.serverConfigs.error = error?.toString();
      console.error('获取服务端配置失败:', error);
    }

    return status;
  }
}
