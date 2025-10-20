import axios from 'axios';
import { message } from 'antd';
import { api } from '../utils/api';

interface LoginCredentials {
  email: string;
  password: string;
  remember?: boolean;
  username?: string;
}

interface RegisterData extends LoginCredentials {
  name?: string;
  company?: string;
  bio?: string;
  avatar_url?: string;
}

interface AuthResponse {
  access_token: string;
  token_type: string;
}

interface ForgotPasswordRequest {
  email: string;
}

interface ForgotPasswordResponse {
  message: string;
  contact_info?: string;
  token?: string;
  reset_url?: string;
}

interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

interface UserInfo {
  id: string;
  name: string;
  email: string;
  company?: string;
  bio?: string;
  avatar_url?: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

class AuthService {
  private tokenKey = 'auth_token';
  private userInfoKey = 'user_info';
  private token: string | null = null;

  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    try {
      // 直接使用fetch API确保请求格式正确
      const formData = new URLSearchParams();
      formData.append('username', credentials.email);
      formData.append('password', credentials.password);
      
      const response = await fetch(`/api/v1/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: formData
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '登录失败');
      }
      
      const data = await response.json();
      
      // 保存认证信息
      if (credentials.remember) {
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('token_type', data.token_type);
      } else {
        sessionStorage.setItem('access_token', data.access_token);
        sessionStorage.setItem('token_type', data.token_type);
      }
      
      this.setToken(data.access_token);
      this.fetchAndStoreUserInfo(); // 登录后立即获取用户信息
      
      return data;
    } catch (error) {
      console.error('登录错误:', error);
      message.error(error instanceof Error ? error.message : '登录失败，请稍后重试');
      throw error;
    }
  }
  
  async register(userData: RegisterData): Promise<AuthResponse> {
    try {
      const data = await api.post<AuthResponse>('/v1/auth/register', userData, { skipAuth: true });
      
      // 保存认证信息
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('token_type', data.token_type);
      
      return data;
    } catch (error) {
      console.error('注册错误:', error);
      message.error(error instanceof Error ? error.message : '注册失败，请稍后重试');
      throw error;
    }
  }
  
  logout(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('token_type');
    sessionStorage.removeItem('access_token');
    sessionStorage.removeItem('token_type');
    
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userInfoKey);
    
    // 可以添加重定向到登录页的逻辑
    window.location.href = '/login';
  }
  
  isAuthenticated(): boolean {
    return !!(localStorage.getItem('access_token') || sessionStorage.getItem('access_token'));
  }
  
  getToken(): string | null {
    // 首先尝试从sessionStorage获取（未勾选"记住我"的情况）
    let token = sessionStorage.getItem('access_token');
    
    // 如果sessionStorage中没有，尝试从localStorage获取（勾选了"记住我"的情况）
    if (!token) {
      token = localStorage.getItem('access_token');
    }
    
    // 如果两处都没有找到令牌，可能是未登录状态
    if (!token) {
      console.log('未找到认证令牌，用户可能未登录');
    }
    
    return token;
  }

  setToken(token: string): void {
    // 仅在内存中存储当前会话使用的令牌
    // localStorage/sessionStorage 的存储在login方法中处理
    this.token = token;
  }

  // 获取当前登录用户信息
  async getCurrentUser(): Promise<UserInfo | null> {
    // 首先尝试从本地存储获取
    const storedUser = localStorage.getItem(this.userInfoKey);
    if (storedUser) {
      return JSON.parse(storedUser);
    }
    
    // 如果本地没有，从服务器获取
    return this.fetchAndStoreUserInfo();
  }
  
  // 从服务器获取用户信息并存储
  async fetchAndStoreUserInfo(): Promise<UserInfo | null> {
    try {
      const token = this.getToken();
      if (!token) return null;
      
      const response = await axios.get('/api/v1/users/me', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
      
      // 处理响应数据，确保id是字符串类型
      const userData = response.data;
      if (userData && userData.id) {
        userData.id = String(userData.id);
      }
      
      const userInfo = userData as UserInfo;
      localStorage.setItem(this.userInfoKey, JSON.stringify(userInfo));
      return userInfo;
    } catch (error) {
      console.error('获取用户信息失败:', error);
      return null;
    }
  }


  // 同步获取用户信息（从本地存储）
  getCurrentUserSync(): UserInfo | null {
    const storedUser = localStorage.getItem(this.userInfoKey);
    if (storedUser) {
      return JSON.parse(storedUser);
    }
    return null;
  }

  // 检查用户是否为管理员
  isAdmin(): boolean {
    const userInfo = this.getCurrentUserSync();
    return userInfo?.is_admin || false;
  }

  // 忘记密码
  async forgotPassword(email: string): Promise<ForgotPasswordResponse> {
    try {
      const response = await fetch('/api/v1/auth/forgot-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '发送重置邮件失败');
      }

      const result = await response.json();
      
      // 检查是否包含联系管理员的信息
      if (result.contact_info) {
        message.warning(result.message);
        if (result.reset_url) {
          console.log('开发环境重置链接:', result.reset_url);
        }
      } else {
        message.success(result.message);
      }

      return result;
    } catch (error) {
      console.error('忘记密码错误:', error);
      message.error(error instanceof Error ? error.message : '发送重置邮件失败，请稍后重试');
      throw error;
    }
  }

  // 修改密码（已登录用户）
  async changePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
    try {
      const response = await fetch('/api/v1/auth/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Authorization': `Bearer ${this.getToken()}`,
        },
        body: new URLSearchParams({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '修改密码失败');
      }

      return await response.json();
    } catch (error) {
      console.error('修改密码错误:', error);
      message.error(error instanceof Error ? error.message : '修改密码失败，请稍后重试');
      throw error;
    }
  }

  // 重置密码
  async resetPassword(token: string, email: string, newPassword: string): Promise<{ message: string }> {
    try {
      const response = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token, email, new_password: newPassword }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '重置密码失败');
      }

      return await response.json();
    } catch (error) {
      console.error('重置密码错误:', error);
      message.error(error instanceof Error ? error.message : '重置密码失败，请稍后重试');
      throw error;
    }
  }
}

export const authService = new AuthService();

/**
 * 修改当前用户密码
 * @param password 新密码
 * @returns Promise<any>
 */
export async function updateCurrentUserPassword(password: string) {
  return api.put('/users/me', { password });
}