import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Table,
  Space,
  Typography,
  Row,
  Col,
  Steps,
  Form,
  Select,
  Input,
  Checkbox,
  Upload,
  Progress,
  Modal,
  Tag,
  Alert,
  Statistic,
  Tabs,
  message,
  Tooltip,
  Popconfirm
} from 'antd';
import {
  ArrowLeftOutlined,
  PlusOutlined,
  UploadOutlined,
  PlayCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ReloadOutlined,
  AppstoreOutlined,
  ClusterOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { evalscopeService } from '@/services/evalscope.service';
import type { TaskResponse, TaskCreate } from '@/types/evalscope.types';

const { Option, OptGroup } = Select;

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;
const { TextArea } = Input;
const { TabPane } = Tabs;

interface BatchTaskConfig {
  models: string[];
  datasets: string[];
  taskNameTemplate: string;
  limit?: number;
  priority: 'low' | 'normal' | 'high';
  maxConcurrent: number;
  retryOnFailure: boolean;
  notifyOnCompletion: boolean;
}

interface BatchJob {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  progress: number;
  estimatedTime?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  tasks: TaskResponse[];
}

const BatchTasksPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [activeTab, setActiveTab] = useState('create');
  const [currentStep, setCurrentStep] = useState(0);
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<BatchJob | null>(null);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [loading, setLoading] = useState(false);

  // 可用模型和数据集（从API动态加载，不使用硬编码）
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [unifiedModels, setUnifiedModels] = useState<any[]>([]);

  const availableDatasets = [
    'gsm8k', 'arc', 'hellaswag', 'mmlu', 'ceval', 'humaneval', 'mbpp', 'bbh'
  ];

  // 模拟批量任务数据
  const mockBatchJobs: BatchJob[] = [
    {
      id: 'batch_1',
      name: 'Qwen系列模型评测',
      status: 'running',
      totalTasks: 12,
      completedTasks: 8,
      failedTasks: 1,
      progress: 75,
      estimatedTime: '25分钟',
      createdAt: '2025-10-09T08:00:00Z',
      startedAt: '2025-10-09T08:05:00Z',
      tasks: []
    },
    {
      id: 'batch_2', 
      name: 'GPT vs Claude对比测试',
      status: 'completed',
      totalTasks: 8,
      completedTasks: 8,
      failedTasks: 0,
      progress: 100,
      createdAt: '2025-10-08T14:30:00Z',
      startedAt: '2025-10-08T14:35:00Z',
      completedAt: '2025-10-08T16:20:00Z',
      tasks: []
    },
    {
      id: 'batch_3',
      name: '代码生成能力全面评测',
      status: 'pending',
      totalTasks: 20,
      completedTasks: 0,
      failedTasks: 0,
      progress: 0,
      createdAt: '2025-10-09T10:00:00Z',
      tasks: []
    }
  ];

  useEffect(() => {
    setBatchJobs(mockBatchJobs);
    loadUnifiedModels();
  }, []);

  const loadUnifiedModels = async () => {
    try {
      const response = await fetch('/api/v1/unified-models/all', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('access_token')}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setUnifiedModels(data.models || []);
        // 只使用API返回的模型，不合并硬编码列表
        const modelIds = data.models.map((model: any) => model.id);
        setAvailableModels(modelIds);
        console.log('✅ 加载批量任务模型列表:', data.models.length, '个模型');
      } else {
        // 降级到测试接口
        const testResponse = await fetch('/api/v1/unified-models/test/available');
        if (testResponse.ok) {
          const testData = await testResponse.json();
          setUnifiedModels(testData.models || []);
          // 只使用API返回的模型
          const modelIds = testData.models.map((model: any) => model.id);
          setAvailableModels(modelIds);
          console.log('✅ 使用测试批量任务模型列表:', testData.models.length, '个模型');
        } else {
          console.warn('⚠️  无法加载模型列表，请先在【API配置管理】或【大模型管理】中配置模型');
          message.warning('未找到可用模型，请先配置模型');
        }
      }
    } catch (error) {
      console.error('❌ 加载统一模型列表失败:', error);
      message.error('加载模型列表失败');
    }
  };

  const handleCreateBatchJob = async (values: any) => {
    try {
      setLoading(true);
      
      const config: BatchTaskConfig = {
        models: values.models,
        datasets: values.datasets,
        taskNameTemplate: values.taskNameTemplate || '{model}_{dataset}_{timestamp}',
        limit: values.limit,
        priority: values.priority || 'normal',
        maxConcurrent: values.maxConcurrent || 3,
        retryOnFailure: values.retryOnFailure || false,
        notifyOnCompletion: values.notifyOnCompletion || true
      };

      console.log('批量任务配置:', config);

      // 计算总任务数
      const totalTasks = config.models.length * config.datasets.length;
      
      // 创建新的批量作业
      const newJob: BatchJob = {
        id: `batch_${Date.now()}`,
        name: values.jobName,
        status: 'pending',
        totalTasks,
        completedTasks: 0,
        failedTasks: 0,
        progress: 0,
        createdAt: new Date().toISOString(),
        tasks: []
      };

      setBatchJobs([newJob, ...batchJobs]);
      setCreateModalVisible(false);
      message.success(`批量作业创建成功！将创建 ${totalTasks} 个评测任务`);
      
    } catch (error) {
      console.error('创建批量任务失败:', error);
      message.error('创建批量任务失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleJobAction = async (jobId: string, action: 'start' | 'pause' | 'cancel' | 'delete') => {
    try {
      setLoading(true);
      
      setBatchJobs(jobs => jobs.map(job => {
        if (job.id === jobId) {
          switch (action) {
            case 'start':
              return { ...job, status: 'running', startedAt: new Date().toISOString() };
            case 'pause':
              return { ...job, status: 'paused' };
            case 'cancel':
              return { ...job, status: 'cancelled' };
            case 'delete':
              return job; // Will be filtered out below
            default:
              return job;
          }
        }
        return job;
      }).filter(job => !(action === 'delete' && job.id === jobId)));

      const actionMap = {
        start: '启动',
        pause: '暂停', 
        cancel: '取消',
        delete: '删除'
      };
      
      message.success(`批量作业${actionMap[action]}成功`);
      
    } catch (error) {
      console.error(`批量作业${action}失败:`, error);
      message.error('操作失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colorMap: { [key: string]: string } = {
      'pending': 'default',
      'running': 'blue',
      'paused': 'orange',
      'completed': 'green',
      'failed': 'red',
      'cancelled': 'default'
    };
    return colorMap[status] || 'default';
  };

  const getStatusIcon = (status: string) => {
    const iconMap: { [key: string]: React.ReactNode } = {
      'pending': <ClockCircleOutlined />,
      'running': <PlayCircleOutlined />,
      'paused': <StopOutlined />,
      'completed': <CheckCircleOutlined />,
      'failed': <CloseCircleOutlined />,
      'cancelled': <CloseCircleOutlined />
    };
    return iconMap[status] || <ClockCircleOutlined />;
  };

  const batchJobColumns = [
    {
      title: '作业名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: BatchJob) => (
        <Space>
          <Text strong>{text}</Text>
          <Text type="secondary">({record.id})</Text>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)} icon={getStatusIcon(status)}>
          {status}
        </Tag>
      )
    },
    {
      title: '预计时间',
      dataIndex: 'estimatedTime',
      key: 'estimatedTime',
      render: (time?: string) => time || '-'
    },
    {
      title: '创建时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString()
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: BatchJob) => (
        <Space>
          {record.status === 'pending' && (
            <Button 
              size="small" 
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleJobAction(record.id, 'start')}
            >
              启动
            </Button>
          )}
          {record.status === 'running' && (
            <Button 
              size="small"
              icon={<StopOutlined />}
              onClick={() => handleJobAction(record.id, 'pause')}
            >
              暂停
            </Button>
          )}
          {record.status === 'paused' && (
            <Button 
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={() => handleJobAction(record.id, 'start')}
            >
              继续
            </Button>
          )}
          <Button 
            size="small"
            icon={<ClusterOutlined />}
            onClick={() => {
              setSelectedJob(record);
              setDetailModalVisible(true);
            }}
          >
            详情
          </Button>
          {['pending', 'paused', 'failed'].includes(record.status) && (
            <Popconfirm
              title="确定删除此批量作业？"
              onConfirm={() => handleJobAction(record.id, 'delete')}
            >
              <Button size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
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
              <AppstoreOutlined /> 批量任务管理
            </Title>
          </Space>
        </Col>
        <Col>
          <Button 
            type="primary" 
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            创建批量作业
          </Button>
        </Col>
      </Row>

      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总作业数"
              value={batchJobs.length}
              prefix={<ClusterOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="运行中"
              value={batchJobs.filter(job => job.status === 'running').length}
              prefix={<PlayCircleOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="已完成"
              value={batchJobs.filter(job => job.status === 'completed').length}
              prefix={<CheckCircleOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总任务数"
              value={batchJobs.reduce((sum, job) => sum + job.totalTasks, 0)}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 作业列表 */}
      <Card title="批量作业列表">
        <Table
          dataSource={batchJobs}
          columns={batchJobColumns}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 创建批量作业Modal */}
      <Modal
        title="创建批量评测作业"
        open={createModalVisible}
        onCancel={() => setCreateModalVisible(false)}
        onOk={() => form.submit()}
        okText="创建作业"
        cancelText="取消"
        width={800}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateBatchJob}
        >
          <Form.Item
            name="jobName"
            label="作业名称"
            rules={[{ required: true, message: '请输入作业名称' }]}
          >
            <Input placeholder="输入批量作业名称" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="models"
                label="选择模型"
                rules={[{ required: true, message: '请选择至少一个模型' }]}
              >
                <Select
                  mode="multiple"
                  placeholder="选择要评测的模型"
                  showSearch
                >
                  {unifiedModels.length > 0 && (
                    <OptGroup label="统一管理的模型">
                      {unifiedModels.map(model => (
                        <Option key={model.id} value={model.id}>
                          {model.display_name} ({model.model_type})
                        </Option>
                      ))}
                    </OptGroup>
                  )}
                  <OptGroup label="预设模型">
                    {availableModels.filter(model => 
                      !unifiedModels.some(um => um.id === model)
                    ).map(model => (
                      <Option key={model} value={model}>
                        {model}
                      </Option>
                    ))}
                  </OptGroup>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="datasets"
                label="选择数据集"
                rules={[{ required: true, message: '请选择至少一个数据集' }]}
              >
                <Select
                  mode="multiple"
                  placeholder="选择评测数据集"
                  showSearch
                >
                  {availableDatasets.map(dataset => (
                    <Option key={dataset} value={dataset}>{dataset}</Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="limit"
                label="样本限制"
                tooltip="限制每个任务的样本数量，用于快速测试"
              >
                <Input type="number" placeholder="如: 10" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="priority"
                label="优先级"
                initialValue="normal"
              >
                <Select>
                  <Option value="low">低</Option>
                  <Option value="normal">普通</Option>
                  <Option value="high">高</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="maxConcurrent"
                label="最大并发数"
                initialValue={3}
                tooltip="同时运行的最大任务数量"
              >
                <Input type="number" min={1} max={10} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="taskNameTemplate"
            label="任务名称模板"
            initialValue="{model}_{dataset}_{timestamp}"
            tooltip="支持变量: {model}, {dataset}, {timestamp}"
          >
            <Input placeholder="{model}_{dataset}_{timestamp}" />
          </Form.Item>

          <Form.Item label="高级选项">
            <Space direction="vertical">
              <Form.Item name="retryOnFailure" valuePropName="checked" noStyle>
                <Checkbox>失败时自动重试</Checkbox>
              </Form.Item>
              <Form.Item name="notifyOnCompletion" valuePropName="checked" initialValue={true} noStyle>
                <Checkbox>完成时发送通知</Checkbox>
              </Form.Item>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 作业详情Modal */}
      <Modal
        title={`批量作业详情: ${selectedJob?.name}`}
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={null}
        width={1000}
      >
        {selectedJob && (
          <div>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={8}>
                <Statistic title="总任务" value={selectedJob.totalTasks} />
              </Col>
              <Col span={8}>
                <Statistic 
                  title="已完成" 
                  value={selectedJob.completedTasks}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Col>
              <Col span={8}>
                <Statistic 
                  title="失败" 
                  value={selectedJob.failedTasks}
                  valueStyle={{ color: '#ff4d4f' }}
                />
              </Col>
            </Row>
            
            <Progress 
              percent={selectedJob.progress}
              status={selectedJob.status === 'failed' ? 'exception' : 'active'}
              style={{ marginBottom: 16 }}
            />

            <Alert
              message="任务列表加载中..."
              description="详细的子任务状态和结果将在这里显示"
              type="info"
            />
          </div>
        )}
      </Modal>
    </div>
  );
};

export default BatchTasksPage;
