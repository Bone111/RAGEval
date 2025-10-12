import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Row,
  Col,
  Typography,
  Statistic,
  Progress,
  Table,
  Tag,
  Space,
  Button,
  Alert,
  Tabs,
  Select,
  DatePicker,
  Switch,
  Tooltip,
  Badge,
  Collapse,
  List,
  Divider
} from 'antd';
import {
  ArrowLeftOutlined,
  DashboardOutlined,
  ThunderboltOutlined,
  CloudServerOutlined,
  BarChartOutlined,
  ReloadOutlined,
  SettingOutlined,
  WarningOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  EnvironmentOutlined,
  BugOutlined,
  InfoCircleOutlined,
  ExclamationCircleOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';
import axios from 'axios';

const { Title, Text } = Typography;
const { TabPane } = Tabs;
const { Option } = Select;
const { RangePicker } = DatePicker;
const { Panel } = Collapse;

interface SystemMetrics {
  cpu: {
    usage: number;
    cores: number;
    temperature?: number;
  };
  memory: {
    used: number;
    total: number;
    available: number;
    usage: number;
  };
  gpu?: {
    usage: number;
    memory: {
      used: number;
      total: number;
    };
    temperature: number;
  };
  disk: {
    used: number;
    total: number;
    usage: number;
  };
  network: {
    download: number;
    upload: number;
  };
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'error';
  uptime: string;
  cpu: number;
  memory: number;
  port?: number;
  version?: string;
}

interface TaskMetrics {
  queue_size: number;
  running_tasks: number;
  completed_today: number;
  failed_today: number;
  avg_execution_time: number;
  success_rate: number;
}

interface EnvironmentCheck {
  overall_status: string;
  timestamp: string;
  python_info: {
    version: string;
    executable: string;
    platform: string;
    path: string[];
  };
  python_packages: {
    [key: string]: {
      installed: boolean;
      version?: string;
      path?: string;
      error?: string;
    };
  };
  command_tools: {
    [key: string]: {
      available: boolean;
      path?: string;
      error?: string;
    };
  };
  services: {
    [key: string]: {
      running: boolean;
      port?: number;
      status: string;
      error?: string;
    };
  };
  environment_variables: {
    [key: string]: string | null;
  };
  work_directories: {
    [key: string]: {
      path: string;
      exists: boolean;
      writable: boolean;
      error?: string;
    };
  };
  cache_directories: {
    [key: string]: {
      path: string;
      exists: boolean;
      writable: boolean;
      error?: string;
    };
  };
  critical_status: {
    packages_ok: boolean;
    services_ok: boolean;
    overall_ok: boolean;
  };
}

interface EnvironmentSummary {
  overall_status: string;
  summary: {
    packages: {
      total: number;
      installed: number;
      missing: number;
    };
    services: {
      total: number;
      running: number;
      stopped: number;
    };
    issues: {
      total: number;
      critical: number;
      warnings: number;
    };
  };
  issues: Array<{
    type: string;
    name: string;
    severity: string;
    message: string;
    solution: string;
  }>;
  recommendations: string[];
}

const SystemMonitorPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(5000);
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
    cpu: { usage: 0, cores: 8 },
    memory: { used: 0, total: 32, available: 0, usage: 0 },
    gpu: { usage: 0, memory: { used: 0, total: 24 }, temperature: 0 },
    disk: { used: 0, total: 1000, usage: 0 },
    network: { download: 0, upload: 0 }
  });
  
  const [services, setServices] = useState<ServiceStatus[]>([
    {
      name: 'FastAPI Backend',
      status: 'running',
      uptime: '2d 14h 32m',
      cpu: 15.2,
      memory: 1.8,
      port: 8000,
      version: '1.0.0'
    },
    {
      name: 'Celery Worker',
      status: 'running',
      uptime: '2d 14h 30m', 
      cpu: 8.5,
      memory: 2.4,
      version: '5.4.0'
    },
    {
      name: 'Redis',
      status: 'running',
      uptime: '7d 2h 15m',
      cpu: 2.1,
      memory: 0.5,
      port: 6379,
      version: '7.2.0'
    },
    {
      name: 'PostgreSQL',
      status: 'running',
      uptime: '7d 2h 16m',
      cpu: 3.8,
      memory: 1.2,
      port: 5432,
      version: '15.4'
    },
    {
      name: 'Frontend Server',
      status: 'running',
      uptime: '1d 8h 45m',
      cpu: 1.2,
      memory: 0.8,
      port: 5173,
      version: '1.0.0'
    }
  ]);

  const [taskMetrics, setTaskMetrics] = useState<TaskMetrics>({
    queue_size: 12,
    running_tasks: 3,
    completed_today: 47,
    failed_today: 2, 
    avg_execution_time: 8.5,
    success_rate: 96.0
  });

  const [environmentCheck, setEnvironmentCheck] = useState<EnvironmentCheck | null>(null);
  const [environmentSummary, setEnvironmentSummary] = useState<EnvironmentSummary | null>(null);
  const [loadingEnvironment, setLoadingEnvironment] = useState(false);

  // 模拟实时数据更新
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      // 模拟系统指标变化
      setSystemMetrics(prev => ({
        cpu: {
          ...prev.cpu,
          usage: Math.max(0, Math.min(100, prev.cpu.usage + (Math.random() - 0.5) * 10))
        },
        memory: {
          ...prev.memory,
          usage: Math.max(0, Math.min(100, prev.memory.usage + (Math.random() - 0.5) * 5))
        },
        gpu: prev.gpu ? {
          ...prev.gpu,
          usage: Math.max(0, Math.min(100, prev.gpu.usage + (Math.random() - 0.5) * 15)),
          temperature: Math.max(30, Math.min(90, prev.gpu.temperature + (Math.random() - 0.5) * 5))
        } : undefined,
        disk: prev.disk,
        network: {
          download: Math.max(0, prev.network.download + (Math.random() - 0.5) * 50),
          upload: Math.max(0, prev.network.upload + (Math.random() - 0.5) * 20)
        }
      }));

      // 模拟任务指标变化
      setTaskMetrics(prev => ({
        ...prev,
        queue_size: Math.max(0, prev.queue_size + Math.floor((Math.random() - 0.5) * 3)),
        running_tasks: Math.max(0, Math.min(10, prev.running_tasks + Math.floor((Math.random() - 0.5) * 2)))
      }));
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval]);

  // 初始化系统指标
  useEffect(() => {
    setSystemMetrics({
      cpu: { usage: 45, cores: 8, temperature: 65 },
      memory: { used: 18, total: 32, available: 14, usage: 56 },
      gpu: { usage: 72, memory: { used: 16, total: 24 }, temperature: 78 },
      disk: { used: 650, total: 1000, usage: 65 },
      network: { download: 125, upload: 45 }
    });
  }, []);

  // 获取环境检查数据
  const fetchEnvironmentCheck = async () => {
    setLoadingEnvironment(true);
    try {
      const [checkResponse, summaryResponse] = await Promise.all([
        axios.get('/api/v1/system/environment-check'),
        axios.get('/api/v1/system/environment-check/summary')
      ]);
      
      setEnvironmentCheck(checkResponse.data);
      setEnvironmentSummary(summaryResponse.data);
    } catch (error) {
      console.error('获取环境检查数据失败:', error);
    } finally {
      setLoadingEnvironment(false);
    }
  };

  // 初始化环境检查
  useEffect(() => {
    fetchEnvironmentCheck();
  }, []);

  const getStatusColor = (status: string) => {
    const colorMap: { [key: string]: string } = {
      running: 'success',
      stopped: 'default',
      error: 'error'
    };
    return colorMap[status] || 'default';
  };

  const getStatusIcon = (status: string) => {
    const iconMap: { [key: string]: React.ReactNode } = {
      running: <CheckCircleOutlined />,
      stopped: <CloseCircleOutlined />,
      error: <WarningOutlined />
    };
    return iconMap[status] || <ClockCircleOutlined />;
  };

  const serviceColumns = [
    {
      title: '服务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ServiceStatus) => (
        <Space>
          <Text strong>{text}</Text>
          {record.version && <Text type="secondary">v{record.version}</Text>}
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Badge 
          status={getStatusColor(status) as any}
          text={
            <Space>
              {getStatusIcon(status)}
              {status}
            </Space>
          }
        />
      )
    },
    {
      title: '运行时间',
      dataIndex: 'uptime',
      key: 'uptime'
    },
    {
      title: 'CPU使用率',
      dataIndex: 'cpu',
      key: 'cpu',
      render: (value: number) => (
        <Progress
          percent={value}
          size="small"
          status={value > 80 ? 'exception' : value > 60 ? 'active' : 'success'}
          format={(percent) => `${percent?.toFixed(1)}%`}
        />
      )
    },
    {
      title: '内存使用',
      dataIndex: 'memory',
      key: 'memory',
      render: (value: number) => (
        <Text>{value.toFixed(1)} GB</Text>
      )
    },
    {
      title: '端口',
      dataIndex: 'port',
      key: 'port',
      render: (port?: number) => port ? <Tag color="blue">{port}</Tag> : '-'
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 头部 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button 
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/evalscope')}
            >
              返回
            </Button>
            <Title level={2} style={{ margin: 0 }}>
              <DashboardOutlined /> 系统监控
            </Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Text type="secondary">自动刷新:</Text>
            <Switch 
              checked={autoRefresh}
              onChange={setAutoRefresh}
              size="small"
            />
            <Select
              value={refreshInterval}
              onChange={setRefreshInterval}
              size="small"
              style={{ width: 80 }}
              disabled={!autoRefresh}
            >
              <Option value={1000}>1s</Option>
              <Option value={5000}>5s</Option>
              <Option value={10000}>10s</Option>
              <Option value={30000}>30s</Option>
            </Select>
            <Button 
              icon={<ReloadOutlined />}
              onClick={() => {
                // 手动刷新逻辑
                console.log('手动刷新');
                if (activeTab === 'environment') {
                  fetchEnvironmentCheck();
                }
              }}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        {/* 系统概览 */}
        <TabPane tab="系统概览" key="overview">
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="CPU使用率"
                  value={systemMetrics.cpu.usage}
                  precision={1}
                  suffix="%"
                  prefix={<ThunderboltOutlined />}
                  valueStyle={{ 
                    color: systemMetrics.cpu.usage > 80 ? '#ff4d4f' : 
                           systemMetrics.cpu.usage > 60 ? '#faad14' : '#52c41a'
                  }}
                />
                <Progress 
                  percent={systemMetrics.cpu.usage} 
                  size="small" 
                  style={{ marginTop: 8 }}
                  status={
                    systemMetrics.cpu.usage > 80 ? 'exception' :
                    systemMetrics.cpu.usage > 60 ? 'active' : 'success'
                  }
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="内存使用率"
                  value={systemMetrics.memory.usage}
                  precision={1}
                  suffix="%"
                  prefix={<CloudServerOutlined />}
                  valueStyle={{
                    color: systemMetrics.memory.usage > 80 ? '#ff4d4f' :
                           systemMetrics.memory.usage > 60 ? '#faad14' : '#52c41a'
                  }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {systemMetrics.memory.used}GB / {systemMetrics.memory.total}GB
                </Text>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="GPU使用率"
                  value={systemMetrics.gpu?.usage || 0}
                  precision={1}
                  suffix="%"
                  prefix={<BarChartOutlined />}
                  valueStyle={{
                    color: (systemMetrics.gpu?.usage || 0) > 80 ? '#ff4d4f' :
                           (systemMetrics.gpu?.usage || 0) > 60 ? '#faad14' : '#52c41a'
                  }}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  温度: {systemMetrics.gpu?.temperature || 0}°C
                </Text>
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="磁盘使用率"
                  value={systemMetrics.disk.usage}
                  precision={1}
                  suffix="%"
                  prefix={<CloudServerOutlined />}
                />
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {systemMetrics.disk.used}GB / {systemMetrics.disk.total}GB
                </Text>
              </Card>
            </Col>
          </Row>

          {/* 网络流量 */}
          <Card title="网络流量" style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="下载速度"
                  value={systemMetrics.network.download}
                  precision={1}
                  suffix="MB/s"
                  valueStyle={{ color: '#1890ff' }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="上传速度"
                  value={systemMetrics.network.upload}
                  precision={1}
                  suffix="MB/s"
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
            </Row>
          </Card>

          {/* 系统警报 */}
          <Card title="系统警报">
            <Space direction="vertical" style={{ width: '100%' }}>
              {systemMetrics.cpu.usage > 85 && (
                <Alert
                  message="CPU使用率过高"
                  description={`当前CPU使用率为 ${systemMetrics.cpu.usage.toFixed(1)}%，建议检查运行中的任务`}
                  type="warning"
                  showIcon
                />
              )}
              {systemMetrics.memory.usage > 90 && (
                <Alert
                  message="内存使用率过高"
                  description={`当前内存使用率为 ${systemMetrics.memory.usage.toFixed(1)}%，可能影响系统性能`}
                  type="error"
                  showIcon
                />
              )}
              {(systemMetrics.gpu?.temperature || 0) > 85 && (
                <Alert
                  message="GPU温度过高"
                  description={`当前GPU温度为 ${systemMetrics.gpu?.temperature}°C，请检查散热`}
                  type="warning"
                  showIcon
                />
              )}
              {taskMetrics.queue_size > 20 && (
                <Alert
                  message="任务队列积压"
                  description={`当前有 ${taskMetrics.queue_size} 个任务在队列中等待，建议增加worker数量`}
                  type="info"
                  showIcon
                />
              )}
            </Space>
          </Card>
        </TabPane>

        {/* 服务状态 */}
        <TabPane tab="服务状态" key="services">
          <Card title="服务运行状态">
            <Table
              dataSource={services}
              columns={serviceColumns}
              rowKey="name"
              pagination={false}
            />
          </Card>
        </TabPane>

        {/* 任务监控 */}
        <TabPane tab="任务监控" key="tasks">
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="队列任务"
                  value={taskMetrics.queue_size}
                  prefix={<ClockCircleOutlined />}
                  valueStyle={{ color: taskMetrics.queue_size > 10 ? '#faad14' : '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="运行中任务"
                  value={taskMetrics.running_tasks}
                  prefix={<ThunderboltOutlined />}
                  valueStyle={{ color: '#1890ff' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="今日完成"
                  value={taskMetrics.completed_today}
                  prefix={<CheckCircleOutlined />}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic
                  title="成功率"
                  value={taskMetrics.success_rate}
                  precision={1}
                  suffix="%"
                  prefix={<BarChartOutlined />}
                  valueStyle={{ 
                    color: taskMetrics.success_rate > 95 ? '#52c41a' :
                           taskMetrics.success_rate > 85 ? '#faad14' : '#ff4d4f'
                  }}
                />
              </Card>
            </Col>
          </Row>

          <Card title="任务执行统计">
            <Row gutter={16}>
              <Col span={12}>
                <Statistic
                  title="平均执行时间"
                  value={taskMetrics.avg_execution_time}
                  precision={1}
                  suffix="分钟"
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title="今日失败"
                  value={taskMetrics.failed_today}
                  valueStyle={{ color: taskMetrics.failed_today > 0 ? '#ff4d4f' : '#52c41a' }}
                />
              </Col>
            </Row>
          </Card>
        </TabPane>

        {/* 环境检查 */}
        <TabPane tab="环境检查" key="environment">
          {loadingEnvironment ? (
            <Card loading>
              <div style={{ height: 200 }} />
            </Card>
          ) : environmentSummary ? (
            <div>
              {/* 环境状态概览 */}
              <Row gutter={16} style={{ marginBottom: 24 }}>
                <Col span={6}>
                  <Card>
                    <Statistic
                      title="总体状态"
                      value={environmentSummary.overall_status}
                      prefix={
                        environmentSummary.overall_status === 'healthy' ? 
                        <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                        <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
                      }
                      valueStyle={{ 
                        color: environmentSummary.overall_status === 'healthy' ? '#52c41a' : '#ff4d4f'
                      }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic
                      title="Python包"
                      value={environmentSummary.summary.packages.installed}
                      suffix={`/ ${environmentSummary.summary.packages.total}`}
                      prefix={<EnvironmentOutlined />}
                      valueStyle={{ 
                        color: environmentSummary.summary.packages.missing === 0 ? '#52c41a' : '#faad14'
                      }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic
                      title="服务状态"
                      value={environmentSummary.summary.services.running}
                      suffix={`/ ${environmentSummary.summary.services.total}`}
                      prefix={<CloudServerOutlined />}
                      valueStyle={{ 
                        color: environmentSummary.summary.services.stopped === 0 ? '#52c41a' : '#faad14'
                      }}
                    />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic
                      title="问题数量"
                      value={environmentSummary.summary.issues.total}
                      prefix={<BugOutlined />}
                      valueStyle={{ 
                        color: environmentSummary.summary.issues.critical > 0 ? '#ff4d4f' :
                               environmentSummary.summary.issues.warnings > 0 ? '#faad14' : '#52c41a'
                      }}
                    />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      严重: {environmentSummary.summary.issues.critical}, 警告: {environmentSummary.summary.issues.warnings}
                    </Text>
                  </Card>
                </Col>
              </Row>

              {/* 问题列表 */}
              {environmentSummary.issues.length > 0 && (
                <Card title="发现的问题" style={{ marginBottom: 24 }}>
                  <List
                    dataSource={environmentSummary.issues}
                    renderItem={(issue) => (
                      <List.Item>
                        <List.Item.Meta
                          avatar={
                            <Badge 
                              status={issue.severity === 'critical' ? 'error' : 'warning'}
                              text={
                                issue.severity === 'critical' ? 
                                <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} /> :
                                <WarningOutlined style={{ color: '#faad14' }} />
                              }
                            />
                          }
                          title={
                            <Space>
                              <Text strong>{issue.message}</Text>
                              <Tag color={issue.severity === 'critical' ? 'red' : 'orange'}>
                                {issue.severity}
                              </Tag>
                            </Space>
                          }
                          description={
                            <div>
                              <Text type="secondary">{issue.solution}</Text>
                            </div>
                          }
                        />
                      </List.Item>
                    )}
                  />
                </Card>
              )}

              {/* 详细环境信息 */}
              {environmentCheck && (
                <Collapse defaultActiveKey={['python', 'services']}>
                  {/* Python环境 */}
                  <Panel header="Python环境" key="python">
                    <Row gutter={16}>
                      <Col span={12}>
                        <Card size="small" title="Python信息">
                          <Space direction="vertical" style={{ width: '100%' }}>
                            <div>
                              <Text strong>版本: </Text>
                              <Text code>{environmentCheck.python_info.version}</Text>
                            </div>
                            <div>
                              <Text strong>可执行文件: </Text>
                              <Text code>{environmentCheck.python_info.executable}</Text>
                            </div>
                            <div>
                              <Text strong>平台: </Text>
                              <Text code>{environmentCheck.python_info.platform}</Text>
                            </div>
                          </Space>
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="Python包状态">
                          <List
                            size="small"
                            dataSource={Object.entries(environmentCheck.python_packages)}
                            renderItem={([name, info]) => (
                              <List.Item>
                                <Space>
                                  {info.installed ? 
                                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                                  }
                                  <Text strong>{name}</Text>
                                  {info.version && <Text type="secondary">v{info.version}</Text>}
                                  {info.error && <Text type="danger">({info.error})</Text>}
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                      </Col>
                    </Row>
                  </Panel>

                  {/* 服务状态 */}
                  <Panel header="服务状态" key="services">
                    <Row gutter={16}>
                      <Col span={12}>
                        <Card size="small" title="运行状态">
                          <List
                            size="small"
                            dataSource={Object.entries(environmentCheck.services)}
                            renderItem={([name, info]) => (
                              <List.Item>
                                <Space>
                                  {info.running ? 
                                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                                  }
                                  <Text strong>{name}</Text>
                                  {info.port && <Tag color="blue">{info.port}</Tag>}
                                  <Tag color={info.running ? 'green' : 'red'}>{info.status}</Tag>
                                  {info.error && <Text type="danger">({info.error})</Text>}
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="命令行工具">
                          <List
                            size="small"
                            dataSource={Object.entries(environmentCheck.command_tools)}
                            renderItem={([name, info]) => (
                              <List.Item>
                                <Space>
                                  {info.available ? 
                                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                                  }
                                  <Text strong>{name}</Text>
                                  {info.path && <Text type="secondary">{info.path}</Text>}
                                  {info.error && <Text type="danger">({info.error})</Text>}
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                      </Col>
                    </Row>
                  </Panel>

                  {/* 环境变量 */}
                  <Panel header="环境变量" key="env_vars">
                    <Card size="small">
                      <List
                        size="small"
                        dataSource={Object.entries(environmentCheck.environment_variables)}
                        renderItem={([name, value]) => (
                          <List.Item>
                            <Space>
                              <Text strong>{name}:</Text>
                              {value ? 
                                <Text code>{value}</Text> :
                                <Text type="danger">未设置</Text>
                              }
                            </Space>
                          </List.Item>
                        )}
                      />
                    </Card>
                  </Panel>

                  {/* 目录权限 */}
                  <Panel header="目录权限" key="directories">
                    <Row gutter={16}>
                      <Col span={12}>
                        <Card size="small" title="工作目录">
                          <List
                            size="small"
                            dataSource={Object.entries(environmentCheck.work_directories)}
                            renderItem={([name, info]) => (
                              <List.Item>
                                <Space>
                                  {info.exists && info.writable ? 
                                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                                  }
                                  <Text strong>{name}</Text>
                                  <Text type="secondary">{info.path}</Text>
                                  <Tag color={info.exists ? 'green' : 'red'}>
                                    {info.exists ? '存在' : '不存在'}
                                  </Tag>
                                  <Tag color={info.writable ? 'green' : 'red'}>
                                    {info.writable ? '可写' : '只读'}
                                  </Tag>
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                      </Col>
                      <Col span={12}>
                        <Card size="small" title="缓存目录">
                          <List
                            size="small"
                            dataSource={Object.entries(environmentCheck.cache_directories)}
                            renderItem={([name, info]) => (
                              <List.Item>
                                <Space>
                                  {info.exists && info.writable ? 
                                    <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                                    <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                                  }
                                  <Text strong>{name}</Text>
                                  <Text type="secondary">{info.path}</Text>
                                  <Tag color={info.exists ? 'green' : 'red'}>
                                    {info.exists ? '存在' : '不存在'}
                                  </Tag>
                                  <Tag color={info.writable ? 'green' : 'red'}>
                                    {info.writable ? '可写' : '只读'}
                                  </Tag>
                                </Space>
                              </List.Item>
                            )}
                          />
                        </Card>
                      </Col>
                    </Row>
                  </Panel>
                </Collapse>
              )}

              {/* 建议 */}
              {environmentSummary.recommendations.length > 0 && (
                <Card title="建议" style={{ marginTop: 24 }}>
                  <List
                    dataSource={environmentSummary.recommendations}
                    renderItem={(recommendation) => (
                      <List.Item>
                        <Space>
                          <InfoCircleOutlined style={{ color: '#1890ff' }} />
                          <Text>{recommendation}</Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                </Card>
              )}
            </div>
          ) : (
            <Card>
              <Alert
                message="无法获取环境检查数据"
                description="请检查后端服务是否正常运行"
                type="error"
                showIcon
              />
            </Card>
          )}
        </TabPane>

        {/* 性能历史 */}
        <TabPane tab="性能历史" key="history">
          <Card title="历史性能数据">
            <Space style={{ marginBottom: 16 }}>
              <Text>时间范围:</Text>
              <RangePicker />
              <Select defaultValue="1h" style={{ width: 100 }}>
                <Option value="1h">1小时</Option>
                <Option value="6h">6小时</Option>
                <Option value="24h">24小时</Option>
                <Option value="7d">7天</Option>
              </Select>
            </Space>
            <Alert
              message="性能历史图表"
              description="这里将显示CPU、内存、GPU使用率的历史趋势图表"
              type="info"
            />
          </Card>
        </TabPane>
      </Tabs>
    </div>
  );
};

export default SystemMonitorPage;


