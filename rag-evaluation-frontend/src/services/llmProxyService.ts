import { api } from '../utils/api';

interface LLMTestResponse {
  success: boolean;
  message: string;
  response?: string;
  error?: any;
}

export async function testLLMConnectivity({ baseUrl, apiKey, modelName, additionalParams }: {
  baseUrl: string;
  apiKey: string;
  modelName: string;
  additionalParams?: any;
}) {
  const data = await api.post<LLMTestResponse>('/llm/llm/test', {
    base_url: baseUrl,
    api_key: apiKey,
    model_name: modelName,
    additional_params: additionalParams
  });
  
  if (data.success) {
    return data.response || '';
  } else {
    throw new Error(data.message || '连接测试失败');
  }
} 