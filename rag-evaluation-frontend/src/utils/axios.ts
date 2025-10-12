/**
 * 配置好的axios实例，包含认证拦截器
 */
import axios, { AxiosError, AxiosResponse } from 'axios';
import { message } from 'antd';
import { authService } from '../services/auth.service';

// 创建axios实例
const axiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000, // 30秒超时
});

// 请求拦截器：自动添加认证头
axiosInstance.interceptors.request.use(
  (config) => {
    const token = authService.getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('DEBUG - Axios请求拦截器添加认证头:', {
        url: config.baseURL + config.url,
        method: config.method?.toUpperCase(),
        token: token.substring(0, 15) + '...' // 只显示令牌前15个字符
      });
    } else {
      console.log('DEBUG - Axios请求拦截器未找到令牌:', {
        url: config.baseURL + config.url,
        method: config.method?.toUpperCase()
      });
    }
    return config;
  },
  (error) => {
    console.error('Axios请求拦截器错误:', error);
    return Promise.reject(error);
  }
);

// 响应拦截器：处理认证错误
axiosInstance.interceptors.response.use(
  (response: AxiosResponse) => {
    console.log('DEBUG - Axios响应成功:', {
      status: response.status,
      url: response.config.url,
      method: response.config.method?.toUpperCase()
    });
    return response;
  },
  (error: AxiosError) => {
    console.error('DEBUG - Axios响应错误:', {
      status: error.response?.status,
      url: error.config?.url,
      method: error.config?.method?.toUpperCase(),
      message: error.message
    });

    // 🔥 优化：处理401认证错误，减少过度的自动登出
    if (error.response?.status === 401) {
      const url = error.config?.url || '';
      
      // 🔥 扩大跳过自动登出的接口范围，避免过度敏感
      const skipAutoLogout = [
        '/v1/unified-models',
        '/v1/users/me',
        '/v1/model-management',
        '/v1/evaluation',
        'refresh-model-names'
      ].some(skipUrl => url.includes(skipUrl));
      
      if (skipAutoLogout) {
        console.log('DEBUG - 检测到401错误但跳过自动登出，URL:', url);
        // 🔥 对于这些接口，只显示警告不强制登出
        message.warning('部分功能需要登录，请检查登录状态');
        return Promise.reject(error);
      } else {
        console.log('DEBUG - 检测到401错误，清除认证信息并重定向到登录页');
        message.error('登录已过期，请重新登录');
        authService.logout();
        return Promise.reject(error);
      }
    }

    // 处理其他HTTP错误
    if (error.response) {
      const errorMessage = error.response.data?.detail || 
                          error.response.data?.message || 
                          `请求失败 (${error.response.status})`;
      message.error(errorMessage);
    } else if (error.request) {
      message.error('网络连接失败，请检查网络设置');
    } else {
      message.error(error.message || '请求配置错误');
    }

    return Promise.reject(error);
  }
);

export default axiosInstance;

