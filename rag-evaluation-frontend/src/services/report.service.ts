import { api } from '../utils/api';

export interface Report {
  id: string;
  title: string;
  description?: string;
  report_type: 'evaluation' | 'performance' | 'comparison';
  public: boolean;
  config?: any;
  content?: any;
  created_at: string;
  updated_at: string;
}

// 移除手动创建报告接口，报告基于评测自动生成

export const reportService = {
  // 获取项目报告列表
  getProjectReports: async (projectId: string): Promise<Report[]> => {
    const response = await api.get<Report[]>(`/v1/reports/?project_id=${projectId}`);
    return response;
  },

  // 获取报告详情
  getReport: async (reportId: string, forceRefresh?: boolean): Promise<Report> => {
    const url = forceRefresh ? `/v1/reports/${reportId}?force_refresh=true` : `/v1/reports/${reportId}`;
    const response = await api.get<Report>(url);
    return response;
  },

  // 删除报告（仅限手动创建的报告）
  deleteReport: async (reportId: string): Promise<void> => {
    await api.delete(`/v1/reports/${reportId}`);
  },

  // 手动生成精度评测报告
  generateAccuracyReport: async (testId: string): Promise<Report> => {
    const response = await api.post<Report>(`/v1/reports/generate/accuracy/${testId}`);
    return response;
  },

  // 手动生成性能测试报告
  generatePerformanceReport: async (testId: string): Promise<Report> => {
    const response = await api.post<Report>(`/v1/reports/generate/performance/${testId}`);
    return response;
  },

  // 生成对比报告
  generateComparisonReport: async (testIds: string[], projectId: string): Promise<Report> => {
    const response = await api.post<Report>('/v1/reports/generate/comparison', {
      test_ids: testIds,
      project_id: projectId
    });
    return response;
  },

  // 导出报告
  exportReport: async (reportId: string, format: string = 'pdf'): Promise<any> => {
    const response = await api.get(`/v1/reports/${reportId}/export?format=${format}`);
    return response;
  },

  // 移除分享功能
};
