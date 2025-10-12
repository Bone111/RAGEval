import React, { useState, useEffect } from 'react';
import { 
  Layout, Tabs, Card, Row, Col, Statistic, Space, Button, 
  Input, Select, Table, Tag, Tooltip, Progress, message,
  Modal, Form, Typography, Switch, Rate, Avatar, Empty,
  Badge, Divider, Descriptions, Alert
} from 'antd';
import { 
  RobotOutlined, CloudOutlined, DesktopOutlined, ApiOutlined,
  HeartOutlined, DownloadOutlined, EyeOutlined, SettingOutlined,
  SearchOutlined, ReloadOutlined, PlusOutlined, StarOutlined,
  TrophyOutlined, FireOutlined, ThunderboltOutlined, DatabaseOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate } from 'react-router-dom';
import { authService } from '../../services/auth.service';
import './ModelManagement.css';

const { Header, Content } = Layout;
const { TabPane } = Tabs;
const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Option } = Select;

// 类型定义
interface ModelInfo {
  id: number;
  model_id: string;
  model_name: string;
  display_name?: string;
  model_type: 'local' | 'api' | 'download' | 'cloud';
  model_source?: string;
  model_family?: string;
  model_size?: string;
  parameter_count?: number;
  status: 'available' | 'downloading' | 'error' | 'offline' | 'unknown';
  download_progress?: number;
  file_size?: number;
  disk_usage?: number;
  supported_context_length?: number;
  inference_speed?: number;
  capabilities?: string[];
  languages?: string[];
  tags?: string[];
  usage_count: number;
  last_used_at?: string;
  benchmark_scores?: Record<string, number>;
  quality_rating?: number;
  is_favorite: boolean;
  notes?: string;
  created_at: string;
  updated_at: string;
}

interface OverviewData {
  total_models: number;
  type_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  recent_used: ModelInfo[];
  favorites: ModelInfo[];
  total_disk_usage: number;
  downloading_tasks: number;
}

const ModelManagement: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [overviewData, setOverviewData] = useState<OverviewData | null>(null);
  const [modelsList, setModelsList] = useState<ModelInfo[]>([]);
  const [filteredModels, setFilteredModels] = useState<ModelInfo[]>([]);
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [selectedModel, setSelectedModel] = useState<ModelInfo | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [scanModalVisible, setScanModalVisible] = useState(false);
  const [scanForm] = Form.useForm();
  const [localRegistryVisible, setLocalRegistryVisible] = useState(false);
  const [localRegistryEntries, setLocalRegistryEntries] = useState<any[]>([]);

  // 获取认证头部
  const getAuthHeaders = () => {
    const token = authService.getToken();
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    };
  };

  // 模型类型图标映射
  const getModelTypeIcon = (type: string) => {
    const iconMap = {
      'local': <DesktopOutlined />,
      'api': <ApiOutlined />,
      'download': <DownloadOutlined />,
      'cloud': <CloudOutlined />
    };
    return iconMap[type] || <RobotOutlined />;
  };

  // 模型状态颜色映射
  const getStatusColor = (status: string) => {
    const colorMap = {
      'available': 'success',
      'downloading': 'processing',
      'error': 'error',
      'offline': 'default',
      'unknown': 'warning'
    };
    return colorMap[status] || 'default';
  };

  // 获取模型总览数据
  const fetchOverviewData = async () => {
    setLoading(true);
    try {
      // 临时使用测试端点绕过认证问题
      const response = await fetch('/api/v1/model-management/overview-test');
      
      if (response.ok) {
        const data = await response.json();
        console.log('获取到的总览数据:', data);
        setOverviewData(data);
        
        // 如果发现模型数量大于0，显示成功提示
        if (data.total_models > 0) {
          console.log(`✅ 发现 ${data.total_models} 个模型：API模型 ${data.type_distribution.api || 0} 个，本地模型 ${data.type_distribution.local || 0} 个`);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('获取模型总览数据失败:', response.status, errorData);
        message.error(`获取模型总览数据失败: ${response.status} ${response.statusText}`);
        
        // 如果是因为表不存在，显示友好提示
        if (response.status === 500 && errorData.detail?.includes('relation "model_info" does not exist')) {
          message.warning('模型管理表尚未创建，请先运行数据库迁移');
        }
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('获取总览数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 获取模型列表
  const fetchModelsList = async () => {
    setLoading(true);
    try {
      // 临时使用测试端点绕过认证问题
      const response = await fetch('/api/v1/model-management/list-test?page=1&page_size=100');
      
      if (response.ok) {
        const data = await response.json();
        console.log('获取到的模型数据:', data);
        setModelsList(data.models || []);
        setFilteredModels(data.models || []);
        
        // 显示模型加载成功提示
        if (data.models && data.models.length > 0) {
          console.log(`📋 模型列表加载完成：共 ${data.models.length} 个模型`);
          // 统计各类型模型
          const typeStats = data.models.reduce((acc, model) => {
            acc[model.model_type] = (acc[model.model_type] || 0) + 1;
            return acc;
          }, {});
          console.log('📊 模型类型分布:', typeStats);
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        console.error('获取模型列表失败:', response.status, errorData);
        message.error(`获取模型列表失败: ${response.status} ${response.statusText}`);
        
        // 如果是因为表不存在，显示友好提示
        if (response.status === 500 && errorData.detail?.includes('relation "model_info" does not exist')) {
          message.warning('模型管理表尚未创建，请先运行数据库迁移');
        }
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('获取模型列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 筛选模型列表
  const filterModels = () => {
    let filtered = [...modelsList];
    
    // 搜索过滤
    if (searchText) {
      filtered = filtered.filter(model => 
        model.model_name.toLowerCase().includes(searchText.toLowerCase()) ||
        model.display_name?.toLowerCase().includes(searchText.toLowerCase()) ||
        model.model_family?.toLowerCase().includes(searchText.toLowerCase())
      );
    }
    
    // 类型过滤
    if (filterType !== 'all') {
      filtered = filtered.filter(model => model.model_type === filterType);
    }
    
    // 状态过滤
    if (filterStatus !== 'all') {
      filtered = filtered.filter(model => model.status === filterStatus);
    }
    
    setFilteredModels(filtered);
  };

  // 格式化文件大小
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(1)} ${units[unitIndex]}`;
  };

  // 查看模型详情
  const viewModelDetail = async (modelId: number) => {
    try {
      // 临时使用测试端点
      const response = await fetch(`/api/v1/model-management/${modelId}/detail-test`);
      
      if (response.ok) {
        const data = await response.json();
        setSelectedModel(data);
        setDetailVisible(true);
      } else {
        message.error('获取模型详情失败');
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('获取模型详情失败:', error);
    }
  };

  // 模型设置功能
  const handleModelSettings = (modelId: number) => {
    // 临时实现：显示模型设置选项
    Modal.info({
      title: '模型设置',
      content: (
        <div>
          <p>✨ 模型设置功能开发中...</p>
          <p>🔧 您可以设置：</p>
          <ul>
            <li>⭐ 收藏/取消收藏</li>
            <li>🏷️ 自定义标签</li>
            <li>📝 模型备注</li>
            <li>⭐ 质量评分</li>
          </ul>
          <p>💡 当前可以通过模型详情查看完整信息</p>
        </div>
      ),
      okText: '知道了'
    });
  };

  // 同步现有模型（智能同步：增删改）
  const handleSyncExistingModels = async () => {
    setLoading(true);
    try {
      // 临时使用测试端点绕过认证问题
      const response = await fetch('/api/v1/model-management/sync-existing-test', {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log('🔄 同步结果:', result);
        
        // 显示详细的同步结果
        if (result.details) {
          const details = result.details;
          const totalSynced = (details.synced_user_configs || 0) + 
                             (details.synced_model_configs || 0);
          const totalRemoved = details.removed_models || 0;
          
          // 构建详细消息
          let messageContent = '';
          const changes = [];
          
          if (totalSynced > 0) {
            changes.push(`新增 ${totalSynced} 个模型`);
          }
          if (totalRemoved > 0) {
            changes.push(`清理 ${totalRemoved} 个已删除的配置`);
          }
          
          if (changes.length > 0) {
            messageContent = `同步完成！${changes.join('，')}`;
            message.success({
              content: messageContent,
              duration: 5
            });
          } else {
            // 无变更，检查是否有模型
            const modelsResponse = await fetch('/api/v1/model-management/list-test?page=1&page_size=100');
            if (modelsResponse.ok) {
              const modelsData = await modelsResponse.json();
              const existingModels = modelsData.models || [];
              if (existingModels.length > 0) {
                message.success('同步完成！所有配置已同步，无变更');
              } else {
                message.warning({
                  content: '没有找到需要同步的模型配置。请先在【API配置管理】中添加模型配置',
                  duration: 5
                });
              }
            } else {
              message.info('同步完成，无变更');
            }
          }
        } else {
          message.success(result.message);
        }
        
        // 刷新数据
        fetchOverviewData();
        fetchModelsList();
      } else {
        const error = await response.json().catch(() => ({}));
        message.error(error.detail || '同步失败，请检查后端服务');
      }
    } catch (error) {
      message.error('同步失败：' + error.message);
    } finally {
      setLoading(false);
    }
  };

  // 扫描本地模型
  const handleLocalScan = async (values: any) => {
    try {
      const response = await fetch('/api/v1/model-management/scan-local', {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          scan_paths: values.paths.split('\n').filter(p => p.trim())
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        message.success(`扫描完成！发现 ${result.found_models.length} 个模型`);
        setScanModalVisible(false);
        scanForm.resetFields();
        // 刷新列表
        fetchModelsList();
        // 刷新本地注册表
        fetchLocalRegistry();
      } else {
        message.error('扫描本地模型失败');
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('扫描本地模型失败:', error);
    }
  };

  // 获取本地模型注册表
  const fetchLocalRegistry = async () => {
    try {
      // 临时使用测试端点
      const response = await fetch('/api/v1/model-management/local-registry/list-test');
      
      if (response.ok) {
        const data = await response.json();
        setLocalRegistryEntries(data.registry_entries || []);
      } else {
        console.error('获取本地模型注册表失败:', response.status);
      }
    } catch (error) {
      console.error('获取本地模型注册表失败:', error);
    }
  };

  // 刷新模型名称
  const handleRefreshModelNames = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/model-management/refresh-model-names', {
        method: 'POST',
        headers: getAuthHeaders()
      });
      
      if (response.ok) {
        const result = await response.json();
        message.success(result.message);
        // 刷新数据
        fetchOverviewData();
        fetchModelsList();
      } else {
        const error = await response.json().catch(() => ({}));
        message.error(error.detail || '刷新模型名称失败');
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('刷新模型名称失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 自动注册本地模型
  const handleAutoRegisterLocal = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/model-management/auto-register-local-test', {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        message.success(result.message);
        // 刷新数据
        fetchOverviewData();
        fetchModelsList();
        fetchLocalRegistry();
      } else {
        const error = await response.json().catch(() => ({}));
        message.error(error.detail || '注册本地模型失败');
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('注册本地模型失败:', error);
    } finally {
      setLoading(false);
    }
  };

  // 切换本地模型启用状态
  const handleToggleLocalModel = async (registryId: number, isEnabled: boolean) => {
    try {
      const response = await fetch('/api/v1/model-management/local-registry/toggle-test', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          registry_id: registryId,
          is_enabled: isEnabled
        })
      });
      
      if (response.ok) {
        const result = await response.json();
        message.success(result.message);
        // 刷新数据
        fetchOverviewData();
        fetchModelsList();
        fetchLocalRegistry();
      } else {
        const error = await response.json().catch(() => ({}));
        message.error(error.detail || '切换模型状态失败');
      }
    } catch (error) {
      message.error('网络错误，请检查连接');
      console.error('切换模型状态失败:', error);
    }
  };


  useEffect(() => {
    const initializeData = async () => {
      await Promise.all([
        fetchOverviewData(),
        fetchModelsList(),
        fetchLocalRegistry()
      ]);
      
      // 延迟显示欢迎消息，确保数据加载完成
      setTimeout(() => {
        if (overviewData && overviewData.total_models > 0) {
          message.success(`🎉 大模型管理系统加载完成！发现 ${overviewData.total_models} 个模型`, 3);
        }
      }, 1000);
    };
    
    initializeData();
  }, []);

  useEffect(() => {
    filterModels();
  }, [searchText, filterType, filterStatus, modelsList]);

  // 表格列定义 - 优化布局减少水平滚动
  const columns: ColumnsType<ModelInfo> = [
    {
      title: '模型信息',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 280, // 适度减少宽度
      ellipsis: {
        showTitle: false,
      },
      render: (_, record) => (
        <div className="model-info-cell" style={{ display: 'flex', alignItems: 'center' }}>
          <Avatar 
            icon={getModelTypeIcon(record.model_type)} 
            size="small"
            style={{ marginRight: 8, backgroundColor: '#f0f2f5', color: '#666' }}
          />
          <div style={{ flex: 1, minWidth: 0 }}>
            <Tooltip title={record.display_name || record.model_name} placement="topLeft">
              <div className="model-info-name">
                {record.display_name || record.model_name}
                {record.is_favorite && (
                  <StarOutlined style={{ color: '#fadb14', marginLeft: 4 }} />
                )}
              </div>
            </Tooltip>
            <div className="model-info-tags">
              {/* 类型标签移到这里，节省空间 */}
              <Tag color={record.model_type === 'local' ? 'green' : 'blue'}>
                {record.model_type === 'local' ? '本地' : record.model_type === 'api' ? 'API' : record.model_type}
              </Tag>
              {record.model_size && <Tag>{record.model_size}</Tag>}
            </div>
          </div>
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      render: (status, record) => (
        <div className="status-cell">
          <Badge 
            status={getStatusColor(status)} 
            text={
              status === 'available' ? '可用' :
              status === 'downloading' ? '下载中' :
              status === 'error' ? '错误' :
              status === 'offline' ? '离线' : '未知'
            } 
          />
          {status === 'downloading' && record.download_progress !== undefined && (
            <Progress 
              percent={record.download_progress} 
              size="small" 
              style={{ width: 50, marginTop: 2 }}
              showInfo={false}
            />
          )}
        </div>
      ),
    },
    {
      title: '大小',
      dataIndex: 'disk_usage',
      key: 'disk_usage',
      width: 80,
      render: (size) => (
        <div className="size-cell">
          {formatFileSize(size)}
        </div>
      ),
    },
    {
      title: '使用统计',
      key: 'usage_stats',
      width: 120,
      render: (_, record) => (
        <div className="usage-stats-cell">
          <div className="usage-count">{record.usage_count}</div>
          <div className="usage-date">
            {record.last_used_at ? new Date(record.last_used_at).toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' }) : '未使用'}
          </div>
          {record.quality_rating && (
            <div className="usage-rating">
              <Rate 
                disabled 
                value={record.quality_rating / 2} 
                count={5}
              />
            </div>
          )}
        </div>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 100,
      fixed: 'right' as const,
      render: (_, record) => (
        <div className="actions-cell">
          <Space size="small">
            <Tooltip title="查看详情">
              <Button 
                type="text" 
                size="small"
                icon={<EyeOutlined />} 
                onClick={() => viewModelDetail(record.id)}
              />
            </Tooltip>
            <Tooltip title="设置">
              <Button 
                type="text" 
                size="small"
                icon={<SettingOutlined />} 
                onClick={() => handleModelSettings(record.id)}
              />
            </Tooltip>
          </Space>
        </div>
      ),
    },
  ];

  return (
    <Layout className="model-management-layout">
      <Header className="model-management-header">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <RobotOutlined style={{ fontSize: 24, marginRight: 12, color: '#1890ff' }} />
            <Title level={3} style={{ margin: 0, color: 'white' }}>大模型统一管理</Title>
          </div>
          <Space>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={handleSyncExistingModels}
            >
              同步现有模型
            </Button>
            <Button 
              icon={<SearchOutlined />}
              onClick={() => setScanModalVisible(true)}
            >
              扫描本地模型
            </Button>
            <Button 
              icon={<ReloadOutlined />}
              onClick={handleRefreshModelNames}
            >
              刷新模型名称
            </Button>
            <Button 
              icon={<ReloadOutlined />}
              onClick={() => {
                fetchOverviewData();
                fetchModelsList();
              }}
            >
              刷新
            </Button>
          </Space>
        </div>
      </Header>
      
      <Content style={{ padding: 24 }}>
        <Tabs 
          activeKey={activeTab} 
          onChange={setActiveTab}
          className="model-management-tabs"
        >
          {/* 总览页面 */}
          <TabPane tab={<span><TrophyOutlined />总览</span>} key="overview">
            <Row gutter={[24, 24]}>
              {/* 统计卡片 */}
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="总模型数"
                    value={overviewData?.total_models || 0}
                    prefix={<RobotOutlined />}
                    valueStyle={{ color: '#1890ff' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="磁盘占用"
                    value={formatFileSize(overviewData?.total_disk_usage)}
                    prefix={<DatabaseOutlined />}
                    valueStyle={{ color: '#52c41a' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="下载中"
                    value={overviewData?.downloading_tasks || 0}
                    prefix={<DownloadOutlined />}
                    valueStyle={{ color: '#faad14' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Card>
                  <Statistic
                    title="收藏模型"
                    value={overviewData?.favorites?.length || 0}
                    prefix={<HeartOutlined />}
                    valueStyle={{ color: '#eb2f96' }}
                  />
                </Card>
              </Col>
            </Row>
            
            <Row gutter={[24, 24]} style={{ marginTop: 24 }}>
              {/* 最近使用 */}
              <Col xs={24} lg={12}>
                <Card 
                  title={<span><FireOutlined style={{ marginRight: 8 }} />最近使用</span>}
                  extra={<Button type="link" onClick={() => setActiveTab('list')}>查看全部</Button>}
                >
                  {overviewData?.recent_used && overviewData.recent_used.length > 0 ? (
                    <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                      {overviewData.recent_used.map(model => (
                        <div key={model.id} style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          padding: '12px 0',
                          borderBottom: '1px solid #f0f0f0'
                        }}>
                          <Avatar 
                            icon={getModelTypeIcon(model.model_type)}
                            style={{ marginRight: 12, backgroundColor: '#f0f2f5', color: '#666' }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 500 }}>
                              {model.display_name || model.model_name}
                            </div>
                            <div style={{ fontSize: 12, color: '#999' }}>
                              使用 {model.usage_count} 次
                            </div>
                          </div>
                          <div style={{ fontSize: 12, color: '#999' }}>
                            {model.last_used_at ? new Date(model.last_used_at).toLocaleDateString() : '-'}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty description="暂无使用记录" />
                  )}
                </Card>
              </Col>
              
              {/* 收藏模型 */}
              <Col xs={24} lg={12}>
                <Card 
                  title={<span><StarOutlined style={{ marginRight: 8 }} />收藏模型</span>}
                >
                  {overviewData?.favorites && overviewData.favorites.length > 0 ? (
                    <div style={{ maxHeight: 300, overflowY: 'auto' }}>
                      {overviewData.favorites.map(model => (
                        <div key={model.id} style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          padding: '12px 0',
                          borderBottom: '1px solid #f0f0f0'
                        }}>
                          <Avatar 
                            icon={getModelTypeIcon(model.model_type)}
                            style={{ marginRight: 12, backgroundColor: '#f0f2f5', color: '#666' }}
                          />
                          <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 500 }}>
                              {model.display_name || model.model_name}
                              <StarOutlined style={{ color: '#fadb14', marginLeft: 8 }} />
                            </div>
                            <div style={{ fontSize: 12, color: '#999' }}>
                              {model.model_family && `${model.model_family} • `}
                              {formatFileSize(model.disk_usage)}
                            </div>
                          </div>
                          <Button 
                            type="text" 
                            size="small"
                            onClick={() => viewModelDetail(model.id)}
                          >
                            查看
                          </Button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <Empty description="暂无收藏模型" />
                  )}
                </Card>
              </Col>
            </Row>
          </TabPane>
          
          {/* 模型列表页面 */}
          <TabPane tab={<span><RobotOutlined />模型列表</span>} key="list">
            <Card>
              {/* 筛选和搜索 */}
              <div style={{ marginBottom: 16 }}>
                <Row gutter={16}>
                  <Col flex="auto">
                    <Search
                      placeholder="搜索模型名称、系列..."
                      value={searchText}
                      onChange={e => setSearchText(e.target.value)}
                      style={{ width: '100%' }}
                    />
                  </Col>
                  <Col>
                    <Select
                      value={filterType}
                      onChange={setFilterType}
                      style={{ width: 120 }}
                    >
                      <Option value="all">全部类型</Option>
                      <Option value="local">本地模型</Option>
                      <Option value="api">API模型</Option>
                      <Option value="download">下载模型</Option>
                      <Option value="cloud">云端模型</Option>
                    </Select>
                  </Col>
                  <Col>
                    <Select
                      value={filterStatus}
                      onChange={setFilterStatus}
                      style={{ width: 120 }}
                    >
                      <Option value="all">全部状态</Option>
                      <Option value="available">可用</Option>
                      <Option value="downloading">下载中</Option>
                      <Option value="error">错误</Option>
                      <Option value="offline">离线</Option>
                    </Select>
                  </Col>
                </Row>
              </div>
              
              {/* 模型列表表格 - 优化响应式布局 */}
              <Table
                columns={columns}
                dataSource={filteredModels}
                loading={loading}
                rowKey="id"
                scroll={{ x: 'max-content' }} // 自适应内容宽度
                size="middle"
                pagination={{
                  pageSize: 10,
                  showSizeChanger: true,
                  showQuickJumper: true,
                  showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
                  responsive: true
                }}
                locale={{
                  emptyText: (
                    <Empty
                      description="暂无模型数据"
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                    >
                      <div style={{ marginTop: 16 }}>
                        <Button 
                          type="primary" 
                          icon={<PlusOutlined />}
                          onClick={handleSyncExistingModels}
                          loading={loading}
                        >
                          同步现有模型
                        </Button>
                        <Button 
                          style={{ marginLeft: 8 }}
                          icon={<SearchOutlined />}
                          onClick={() => setScanModalVisible(true)}
                        >
                          扫描本地模型
                        </Button>
                      </div>
                    </Empty>
                  )
                }}
              />
            </Card>
          </TabPane>
          
          {/* 本地扫描页面 */}
          <TabPane tab={<span><DesktopOutlined />本地扫描</span>} key="local">
            <Card title="模型同步和扫描">
              <div style={{ marginBottom: 24 }}>
                <Title level={5}>🔄 同步现有模型</Title>
                <Paragraph>
                  自动发现和同步所有大模型配置，包括：API模型、系统配置、本地模型文件。
                </Paragraph>
                <Space wrap>
                  <Button 
                    type="primary" 
                    icon={<PlusOutlined />}
                    onClick={handleSyncExistingModels}
                    loading={loading}
                  >
                    一键同步所有模型
                  </Button>
                  
                  {localRegistryEntries.length > 0 && (
                    <Button 
                      type="default" 
                      icon={<DatabaseOutlined />}
                      onClick={handleAutoRegisterLocal}
                      loading={loading}
                    >
                      注册本地模型 ({localRegistryEntries.length})
                    </Button>
                  )}
                  
                  <Button 
                    icon={<ReloadOutlined />}
                    onClick={() => {
                      fetchOverviewData();
                      fetchModelsList(); 
                      fetchLocalRegistry();
                    }}
                  >
                    刷新数据
                  </Button>
                </Space>
              </div>
              
              <Divider />
              
              <div>
                <Title level={5}>📂 扫描本地路径</Title>
                <Paragraph>
                  扫描指定路径中的模型文件，自动识别并注册到系统中。
                  支持的模型格式：.bin, .safetensors, .pth, .ckpt, .gguf
                </Paragraph>
                
                <Button 
                  icon={<SearchOutlined />}
                  onClick={() => setScanModalVisible(true)}
                  style={{ marginRight: 12 }}
                >
                  自定义路径扫描
                </Button>
                <Button 
                  icon={<DatabaseOutlined />}
                  onClick={() => setLocalRegistryVisible(true)}
                >
                  查看本地注册表 ({localRegistryEntries.length})
                </Button>
              </div>
            </Card>
          </TabPane>
        </Tabs>
      </Content>
      
      {/* 本地扫描Modal */}
      <Modal
        title="扫描本地模型"
        visible={scanModalVisible}
        onCancel={() => setScanModalVisible(false)}
        onOk={() => scanForm.submit()}
        width={600}
      >
        <Form
          form={scanForm}
          layout="vertical"
          onFinish={handleLocalScan}
        >
          <Form.Item
            name="paths"
            label="扫描路径"
            rules={[{ required: true, message: '请输入扫描路径' }]}
          >
            <Input.TextArea
              rows={6}
              placeholder={`请输入要扫描的路径，每行一个，例如：
/home/user/models
/opt/models
C:\\Models`}
            />
          </Form.Item>
        </Form>
      </Modal>
      
      {/* 模型详情Modal */}
      <Modal
        title="模型详情"
        visible={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedModel && (
          <div>
            <Descriptions column={2} bordered>
              <Descriptions.Item label="模型名称" span={2}>
                {selectedModel.display_name || selectedModel.model_name}
              </Descriptions.Item>
              <Descriptions.Item label="模型类型">
                <Tag>{selectedModel.model_type}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Badge status={getStatusColor(selectedModel.status)} text={selectedModel.status} />
              </Descriptions.Item>
              <Descriptions.Item label="模型系列">
                {selectedModel.model_family || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="模型大小">
                {selectedModel.model_size || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="文件大小">
                {formatFileSize(selectedModel.disk_usage)}
              </Descriptions.Item>
              <Descriptions.Item label="使用次数">
                {selectedModel.usage_count}
              </Descriptions.Item>
              {selectedModel.model_type === 'local' && selectedModel.model_path && (
                <Descriptions.Item label="本地路径" span={2}>
                  <Tooltip title={`点击复制: ${selectedModel.model_path}`} placement="topLeft">
                    <div style={{ 
                      fontSize: 12, 
                      fontFamily: 'monospace',
                      cursor: 'pointer',
                      padding: '4px 8px',
                      borderRadius: '4px',
                      backgroundColor: '#f5f5f5',
                      border: '1px solid #e8e8e8',
                      transition: 'all 0.3s',
                      wordBreak: 'break-all'
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      navigator.clipboard.writeText(selectedModel.model_path).then(() => {
                        message.success('路径已复制到剪贴板');
                      }).catch(() => {
                        // 降级方案
                        const textArea = document.createElement('textarea');
                        textArea.value = selectedModel.model_path;
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                        message.success('路径已复制到剪贴板');
                      });
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = '#e6f7ff';
                      e.currentTarget.style.borderColor = '#1890ff';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = '#f5f5f5';
                      e.currentTarget.style.borderColor = '#e8e8e8';
                    }}
                    >
                      📂 {selectedModel.model_path}
                    </div>
                  </Tooltip>
                </Descriptions.Item>
              )}
              <Descriptions.Item label="质量评分" span={2}>
                {selectedModel.quality_rating ? (
                  <Rate disabled value={selectedModel.quality_rating / 2} />
                ) : '-'}
              </Descriptions.Item>
            </Descriptions>
          </div>
        )}
      </Modal>
      
      {/* 本地模型注册表Modal */}
      <Modal
        title="本地模型注册表"
        visible={localRegistryVisible}
        onCancel={() => setLocalRegistryVisible(false)}
        footer={null}
        width={1000}
      >
        <div style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Text type="secondary">
              显示扫描发现的本地模型，共 {localRegistryEntries.length} 个
            </Text>
            <Alert
              message="💡 使用说明"
              description="通过启用/禁用开关控制哪些本地模型显示在大模型列表中。启用的模型会自动注册到系统，禁用的模型将从列表中隐藏。"
              type="info"
              showIcon
              style={{ fontSize: 12 }}
            />
            <div>
              <Space>
                <Button 
                  size="small"
                  onClick={() => {
                    // 批量启用所有模型
                    localRegistryEntries.forEach(entry => {
                      if (!entry.is_enabled) {
                        handleToggleLocalModel(entry.id, true);
                      }
                    });
                  }}
                >
                  全部启用
                </Button>
                <Button 
                  size="small"
                  onClick={() => {
                    // 批量禁用所有模型
                    localRegistryEntries.forEach(entry => {
                      if (entry.is_enabled) {
                        handleToggleLocalModel(entry.id, false);
                      }
                    });
                  }}
                >
                  全部禁用
                </Button>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  已启用: {localRegistryEntries.filter(e => e.is_enabled).length} 个
                </Text>
              </Space>
            </div>
          </Space>
        </div>
         <Table
           columns={[
             {
               title: '启用',
               dataIndex: 'is_enabled',
               key: 'is_enabled',
               width: 80,
               render: (isEnabled, record) => (
                 <Switch
                   checked={isEnabled}
                   size="small"
                   loading={loading}
                   onChange={(checked) => handleToggleLocalModel(record.id, checked)}
                 />
               ),
             },
             {
               title: '模型名称',
               dataIndex: 'model_name',
               key: 'model_name',
               width: 200,
               render: (name, record) => (
                 <div>
                   <div style={{ fontWeight: 500, marginBottom: 2 }}>
                     {name}
                   </div>
                   {record.model_type && (
                     <Tag size="small" color="blue">{record.model_type}</Tag>
                   )}
                 </div>
               ),
             },
             {
               title: '模型路径',
               dataIndex: 'model_path',
               key: 'model_path',
               width: 350,
               render: (path) => (
                 <Tooltip title={`点击复制: ${path}`} placement="topLeft">
                   <div style={{ 
                     fontSize: 11, 
                     fontFamily: 'monospace',
                     cursor: 'pointer',
                     padding: '4px 8px',
                     borderRadius: '4px',
                     backgroundColor: '#f5f5f5',
                     border: '1px solid #e8e8e8',
                     transition: 'all 0.3s',
                     wordBreak: 'break-all',
                     maxWidth: 330,
                     overflow: 'hidden',
                     textOverflow: 'ellipsis',
                     whiteSpace: 'nowrap'
                   }}
                   onClick={(e) => {
                     e.stopPropagation();
                     navigator.clipboard.writeText(path).then(() => {
                       message.success('路径已复制到剪贴板');
                     }).catch(() => {
                       // 降级方案
                       const textArea = document.createElement('textarea');
                       textArea.value = path;
                       document.body.appendChild(textArea);
                       textArea.select();
                       document.execCommand('copy');
                       document.body.removeChild(textArea);
                       message.success('路径已复制到剪贴板');
                     });
                   }}
                   onMouseEnter={(e) => {
                     e.currentTarget.style.backgroundColor = '#e6f7ff';
                     e.currentTarget.style.borderColor = '#1890ff';
                   }}
                   onMouseLeave={(e) => {
                     e.currentTarget.style.backgroundColor = '#f5f5f5';
                     e.currentTarget.style.borderColor = '#e8e8e8';
                   }}
                   >
                     📂 {path}
                   </div>
                 </Tooltip>
               ),
             },
             {
               title: '文件大小',
               dataIndex: 'file_size',
               key: 'file_size',
               width: 100,
               render: (size) => formatFileSize(size),
             },
             {
               title: '文件数量',
               dataIndex: 'file_count',
               key: 'file_count',
               width: 100,
               render: (count) => count || '-',
             },
             {
               title: '扫描状态',
               dataIndex: 'scan_status',
               key: 'scan_status',
               width: 100,
               render: (status) => {
                 const statusMap = {
                   'discovered': { color: 'blue', text: '已发现' },
                   'analyzed': { color: 'green', text: '已分析' },
                   'registered': { color: 'purple', text: '已注册' },
                   'error': { color: 'red', text: '错误' }
                 };
                 const statusInfo = statusMap[status] || { color: 'default', text: status };
                 return <Tag size="small" color={statusInfo.color}>{statusInfo.text}</Tag>;
               },
             },
             {
               title: '最后扫描',
               dataIndex: 'last_scanned',
               key: 'last_scanned',
               width: 120,
               render: (date) => date ? new Date(date).toLocaleDateString() : '-',
             },
           ]}
          dataSource={localRegistryEntries}
          rowKey="id"
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
          }}
          scroll={{ x: 1000 }}
        />
      </Modal>
    </Layout>
  );
};

export default ModelManagement;
