import { api } from '../utils/api';

export interface MinerUConfigStatus {
  has_config: boolean;
  api_status: 'valid' | 'invalid' | 'error' | 'timeout' | 'unknown';
  error_message?: string;
  config_source: 'environment' | 'frontend' | 'none';
}

export interface MinerUError {
  error: string;
  message: string;
  action: 'configure_mineru' | 'check_key' | 'retry';
  redirect_to?: string;
  status_code?: number;
  api_code?: number;
}

class MinerUService {
  /**
   * 检查MinerU配置状态
   */
  async checkConfigStatus(): Promise<MinerUConfigStatus> {
    try {
      const response = await api.get('/mineru/mineru-config-status');
      console.log('MinerU配置状态响应:', response);
      return response as MinerUConfigStatus;
    } catch (error) {
      console.error('检查MinerU配置状态失败:', error);
      return {
        has_config: false,
        api_status: 'error',
        error_message: '检查配置状态失败',
        config_source: 'none'
      };
    }
  }

  /**
   * 验证MinerU API密钥有效性
   */
  async validateApiKey(apiKey: string): Promise<{
    isValid: boolean;
    error?: string;
    quota?: any;
  }> {
    try {
      const response = await api.post('/mineru/validate-api-key', {
        api_key: apiKey
      }) as any;
      console.log('MinerU密钥验证响应:', response);
      return {
        isValid: response.is_valid,
        error: response.error,
        quota: response.quota
      };
    } catch (error) {
      console.error('验证MinerU API密钥失败:', error);
      return {
        isValid: false,
        error: '验证密钥失败，请检查网络连接'
      };
    }
  }

  /**
   * 解析MinerU错误信息
   */
  parseError(error: any): MinerUError {
    // 如果是HTTPException的detail
    if (error?.response?.data?.detail) {
      const detail = error.response.data.detail;
      if (typeof detail === 'object') {
        return detail as MinerUError;
      } else {
        return {
          error: 'MinerU解析失败',
          message: detail,
          action: 'retry'
        };
      }
    }

    // 如果是普通错误
    if (typeof error === 'string') {
      return {
        error: 'MinerU解析失败',
        message: error,
        action: 'retry'
      };
    }

    // 默认错误
    return {
      error: '未知错误',
      message: '文件解析过程中发生未知错误',
      action: 'retry'
    };
  }

  /**
   * 获取错误提示信息
   */
  getErrorMessage(error: MinerUError): string {
    switch (error.action) {
      case 'configure_mineru':
        return '请先在系统设置中配置MinerU API密钥';
      case 'check_key':
        return '请检查API密钥是否正确或是否已过期';
      case 'retry':
        return '请稍后重试或联系管理员';
      default:
        return error.message;
    }
  }

  /**
   * 获取错误操作建议
   */
  getErrorAction(error: MinerUError): {
    text: string;
    action: () => void;
    type: 'primary' | 'default' | 'link' | 'dashed' | 'text';
  } {
    switch (error.action) {
      case 'configure_mineru':
        return {
          text: '去配置',
          action: () => {
            if (error.redirect_to) {
              window.location.href = error.redirect_to;
            }
          },
          type: 'primary' as const
        };
      case 'check_key':
        return {
          text: '检查密钥',
          action: () => {
            if (error.redirect_to) {
              window.location.href = error.redirect_to;
            }
          },
          type: 'primary' as const
        };
      case 'retry':
        return {
          text: '重试',
          action: () => {
            window.location.reload();
          },
          type: 'default' as const
        };
      default:
        return {
          text: '确定',
          action: () => {},
          type: 'default' as const
        };
    }
  }
}

export const mineruService = new MinerUService();
