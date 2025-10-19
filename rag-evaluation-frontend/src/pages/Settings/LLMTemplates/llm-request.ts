import OpenAI from 'openai';
import type { ChatCompletionMessageParam } from 'openai/resources/chat/completions/completions';
import { ConfigManager, ModelConfig } from '@utils/configManager';


// LLMClient 类，支持 openai 及硅基流动
export class LLMClient {
  private client: OpenAI;
  private modelName: string;
  private baseUrl: string;
  private apiKey: string;
  private additionalParams?: Record<string, any>;

  constructor({ 
    baseUrl, 
    apiKey, 
    modelName, 
    additionalParams 
  }: { 
    baseUrl: string; 
    apiKey: string; 
    modelName: string;
    additionalParams?: Record<string, any>;
  }) {
    this.baseUrl = baseUrl;
    this.apiKey = apiKey;
    this.modelName = modelName;
    this.additionalParams = additionalParams;
    // 移除OpenAI客户端直接实例化，改为通过后端代理
    // this.client = new OpenAI({
    //   apiKey: this.apiKey,
    //   baseURL: this.baseUrl,
    //   dangerouslyAllowBrowser: true,
    // });
  }

  static async getConfigById(configId: string): Promise<ModelConfig | null> {
    const configManager = ConfigManager.getInstance();
    return configManager.getConfig<ModelConfig>(configId, 'model');
  }

  static async createFromConfigId(configId: string): Promise<LLMClient> {
    const config = await this.getConfigById(configId);
    if (!config) {
      throw new Error('Configuration not found');
    }
    let parsedParams;
    if (typeof config.additionalParams === 'string') {
      try {
        parsedParams = JSON.parse(config.additionalParams);
      } catch (err) {
        console.warn('Failed to parse additionalParams:', err);
        parsedParams = undefined;
      }
    } else {
      parsedParams = config.additionalParams;
    }
    
    return new LLMClient({
      baseUrl: config.baseUrl,
      apiKey: config.apiKey,
      modelName: config.modelName,
      additionalParams: parsedParams,
    });
  }

  async chatCompletion({
    userMessage,
    systemMessage = '你是一个有帮助的AI助手。',
    additionalParams = {},
  }: {
    userMessage: string;
    systemMessage?: string;
    additionalParams?: Record<string, any>;
  }): Promise<string> {
    try {
      // 通过后端代理发送请求，避免跨域问题
      const response = await fetch('/api/v1/llm/proxy', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          base_url: this.baseUrl,
          api_key: this.apiKey,
          model_name: this.modelName,
          messages: [
            { role: 'system', content: systemMessage },
            { role: 'user', content: userMessage },
          ],
          ...(this.additionalParams || {}),
          ...additionalParams,
        })
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const data = await response.json();
      const content = data.choices?.[0]?.message?.content?.trim() || '';
      return content;
    } catch (err: any) {
      throw new Error(err.message || '请求异常');
    }
  }
}

export type { ChatCompletionMessageParam };
