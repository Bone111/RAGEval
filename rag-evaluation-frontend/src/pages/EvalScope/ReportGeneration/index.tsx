import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Form,
  Select,
  Checkbox,
  Switch,
  Space,
  Typography,
  Row,
  Col,
  Steps,
  Alert,
  Progress,
  Table,
  Tag,
  Divider,
  message,
  Modal,
  Upload
} from 'antd';
import {
  ArrowLeftOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  DownloadOutlined,
  EyeOutlined,
  SettingOutlined,
  BarChartOutlined,
  ShareAltOutlined,
  UploadOutlined
} from '@ant-design/icons';
import { evalscopeService } from '@/services/evalscope.service';
import type { EvalTask, EvalTaskDetail } from '@/types/evalscope.types';

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;
const { Option } = Select;
const { TextArea } = Form.Item;

interface ReportConfig {
  tasks: string[];
  includeCharts: boolean;
  includeRawData: boolean;
  includeModelComparison: boolean;
  includeSummary: boolean;
  format: 'pdf' | 'excel' | 'both';
  template: 'standard' | 'detailed' | 'executive';
  customTitle?: string;
  customDescription?: string;
}

interface ReportTemplate {
  id: string;
  name: string;
  description: string;
  sections: string[];
  format: string[];
  preview?: string;
  icon?: string;
  color?: string;
  targetAudience?: string;
}

const ReportGenerationPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [tasks, setTasks] = useState<EvalTask[]>([]);
  const [selectedTasks, setSelectedTasks] = useState<number[]>([]);
  const [reportConfig, setReportConfig] = useState<ReportConfig>({
    tasks: [],
    includeCharts: true,
    includeRawData: false,
    includeModelComparison: true,
    includeSummary: true,
    format: 'pdf',
    template: 'standard'
  });
  const [previewVisible, setPreviewVisible] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [previewContent, setPreviewContent] = useState<any>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [formatModalVisible, setFormatModalVisible] = useState(false);
  const [selectedFormat, setSelectedFormat] = useState<'pdf' | 'html'>('pdf');
  const [previewMode, setPreviewMode] = useState<'simple' | 'full'>('simple');

  const templates: ReportTemplate[] = [
    {
      id: 'standard',
      name: '标准报告',
      description: '简洁明了的技术报告，适合日常评测和团队分享',
      sections: ['概览', '模型性能', '数据集结果', '结论'],
      format: ['pdf', 'excel'],
      preview: '包含基础评测指标、性能对比图表和简要结论，适合技术团队日常使用',
      icon: '📊',
      color: '#1890ff',
      targetAudience: '技术团队'
    },
    {
      id: 'detailed', 
      name: '详细报告',
      description: '深度分析报告，包含错误分析和改进建议',
      sections: ['概览', '模型性能', '数据集结果', '错误分析', '对比分析', '建议', '结论'],
      format: ['pdf', 'excel'],
      preview: '包含详细评测数据、错误案例分析、模型对比分析和具体改进建议，适合深度研究',
      icon: '🔍',
      color: '#52c41a',
      targetAudience: '研究人员'
    },
    {
      id: 'executive',
      name: '执行摘要',
      description: '面向管理层的精简报告，突出关键指标和决策建议',
      sections: ['执行摘要', '关键发现', '建议行动'],
      format: ['pdf'],
      preview: '突出关键性能指标、重要发现和行动建议，适合管理层决策参考',
      icon: '📈',
      color: '#fa8c16',
      targetAudience: '管理层'
    }
  ];

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      setLoadingTasks(true);
      
      // 调用后端API获取已完成的任务
      const response = await fetch('/api/v1/reports/tasks/completed');
      
      if (!response.ok) {
        throw new Error('获取任务列表失败');
      }
      
      const data = await response.json();
      setTasks(data.tasks || []);
      
      if (data.tasks && data.tasks.length > 0) {
        console.log(`成功加载 ${data.tasks.length} 个已完成的评测任务`);
      } else {
        console.log('暂无已完成的评测任务');
      }
    } catch (error) {
      console.error('加载任务失败:', error);
      message.error('加载已完成任务失败');
      setTasks([]);
    } finally {
      setLoadingTasks(false);
    }
  };

  const steps = [
    {
      title: '选择任务',
      description: '选择要包含在报告中的评测任务'
    },
    {
      title: '配置报告',
      description: '设置报告格式和内容选项'
    },
    {
      title: '生成报告', 
      description: '生成并下载评测报告'
    }
  ];

  const handleNext = () => {
    if (currentStep === 0 && selectedTasks.length === 0) {
      message.warning('请至少选择一个任务');
      return;
    }
    setCurrentStep(currentStep + 1);
  };

  const handlePrev = () => {
    setCurrentStep(currentStep - 1);
  };

  const handlePreviewReport = async () => {
    if (selectedTasks.length === 0) {
      message.warning('请先选择要预览的任务');
      return;
    }

    try {
      setLoadingPreview(true);
      
      const config = {
        ...reportConfig,
        tasks: selectedTasks
      };

      const response = await fetch('/api/v1/reports/preview', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_ids: selectedTasks.map(id => id.toString()),
          config: config
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '预览失败');
      }

      const previewData = await response.json();
      setPreviewContent(previewData);
      setPreviewVisible(true);
      
    } catch (error) {
      console.error('预览报告失败:', error);
      message.error(`预览失败: ${error.message}`);
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleGenerateReport = async () => {
    // 先显示格式选择弹框
    setFormatModalVisible(true);
  };

  const handleConfirmGenerate = async () => {
    try {
      setGeneratingReport(true);
      setFormatModalVisible(false);
      
      const config = {
        ...reportConfig,
        format: selectedFormat,
        tasks: selectedTasks
      };

      console.log('生成报告配置:', config);

      // 调用后端API生成报告
      const response = await fetch('/api/v1/reports/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_ids: selectedTasks.map(id => id.toString()),
          config: config
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || '生成报告失败');
      }

      // 获取文件名
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `EvalScope_Report_${new Date().toISOString().split('T')[0]}.${selectedFormat}`;
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=([^;]+)/);
        if (filenameMatch) {
          filename = filenameMatch[1];
        }
      }

      // 下载文件
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      message.success(`${selectedFormat.toUpperCase()} 报告生成成功！`);
      
    } catch (error) {
      console.error('生成报告失败:', error);
      message.error(`生成报告失败: ${error.message}`);
    } finally {
      setGeneratingReport(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Card 
            title="选择评测任务" 
            size="small"
            extra={
              <Button 
                size="small" 
                onClick={loadTasks} 
                loading={loadingTasks}
              >
                刷新
              </Button>
            }
          >
            <Alert
              message="选择要包含在报告中的已完成评测任务"
              type="info"
              style={{ marginBottom: 16 }}
            />
            
            {loadingTasks ? (
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <Progress type="circle" size={60} />
                <br />
                <Text type="secondary" style={{ marginTop: 16, display: 'block' }}>
                  正在加载已完成的评测任务...
                </Text>
              </div>
            ) : tasks.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <Text type="secondary" style={{ fontSize: 16 }}>
                  暂无已完成的评测任务
                </Text>
                <br />
                <Text type="secondary" style={{ fontSize: 14 }}>
                  请先在任务管理中创建并完成评测任务
                </Text>
              </div>
            ) : (
              <Table
                rowSelection={{
                  selectedRowKeys: selectedTasks,
                  onChange: (keys) => setSelectedTasks(keys as number[]),
                  type: 'checkbox'
                }}
                dataSource={tasks}
                rowKey="id"
                columns={[
                {
                  title: '任务名称',
                  dataIndex: 'task_name',
                  key: 'task_name'
                },
                {
                  title: '模型',
                  dataIndex: 'model_id', 
                  key: 'model_id',
                  render: (text) => <Tag color="blue">{text}</Tag>
                },
                {
                  title: '数据集',
                  dataIndex: 'datasets',
                  key: 'datasets',
                  render: (datasets: string[]) => (
                    <Space wrap>
                      {datasets.map(dataset => (
                        <Tag key={dataset} color="green">{dataset}</Tag>
                      ))}
                    </Space>
                  )
                },
                {
                  title: '创建时间',
                  dataIndex: 'created_at',
                  key: 'created_at',
                  width: 180,
                  render: (text) => new Date(text).toLocaleString()
                },
                {
                  title: '状态',
                  dataIndex: 'status',
                  key: 'status',
                  render: (status) => (
                    <Tag color={status === 'completed' ? 'green' : 'blue'}>
                      {status}
                    </Tag>
                  )
                }
              ]}
              />
            )}
          </Card>
        );

      case 1:
        return (
          <Row gutter={16}>
            <Col span={12}>
              <Card title="报告模板" size="small">
                {templates.map(template => (
                  <Card
                    key={template.id}
                    size="small"
                    style={{ 
                      marginBottom: 12,
                      border: reportConfig.template === template.id ? `2px solid ${template.color}` : '1px solid #d9d9d9',
                      cursor: 'pointer',
                      backgroundColor: reportConfig.template === template.id ? `${template.color}08` : '#fff'
                    }}
                    onClick={() => setReportConfig({...reportConfig, template: template.id as any})}
                  >
                    <Row justify="space-between" align="top">
                      <Col span={18}>
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space align="center">
                            <Text style={{ fontSize: 16 }}>{template.icon}</Text>
                            <Text strong style={{ color: template.color }}>{template.name}</Text>
                            <Tag color={template.color} size="small">{template.targetAudience}</Tag>
                          </Space>
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {template.description}
                          </Text>
                          <Space wrap>
                            {template.sections.map(section => (
                              <Tag key={section} size="small" color={template.color}>{section}</Tag>
                            ))}
                          </Space>
                          {template.preview && (
                            <div style={{ 
                              backgroundColor: '#f5f5f5', 
                              padding: '8px', 
                              borderRadius: '4px',
                              fontSize: '11px',
                              color: '#666'
                            }}>
                              💡 {template.preview}
                            </div>
                          )}
                        </Space>
                      </Col>
                      <Col span={6} style={{ textAlign: 'right' }}>
                        <Space direction="vertical" size="small">
                          <Button 
                            size="small" 
                            icon={<EyeOutlined />}
                            loading={loadingPreview}
                            onClick={(e) => {
                              e.stopPropagation();
                              setReportConfig({...reportConfig, template: template.id as any});
                              handlePreviewReport();
                            }}
                          >
                            预览
                          </Button>
                          <Text type="secondary" style={{ fontSize: 10 }}>
                            {template.format.join(', ').toUpperCase()}
                          </Text>
                        </Space>
                      </Col>
                    </Row>
                  </Card>
                ))}
              </Card>
            </Col>
            
            <Col span={12}>
              <Card title="报告配置" size="small">
                {/* 当前选择的模板预览 */}
                <div style={{ 
                  backgroundColor: `${templates.find(t => t.id === reportConfig.template)?.color || '#1890ff'}08`,
                  padding: '12px',
                  borderRadius: '6px',
                  marginBottom: '16px',
                  border: `1px solid ${templates.find(t => t.id === reportConfig.template)?.color || '#1890ff'}40`
                }}>
                  <Space align="center" style={{ marginBottom: '8px' }}>
                    <Text style={{ fontSize: 16 }}>
                      {templates.find(t => t.id === reportConfig.template)?.icon}
                    </Text>
                    <Text strong style={{ color: templates.find(t => t.id === reportConfig.template)?.color }}>
                      当前选择: {templates.find(t => t.id === reportConfig.template)?.name}
                    </Text>
                    <Tag color={templates.find(t => t.id === reportConfig.template)?.color}>
                      {templates.find(t => t.id === reportConfig.template)?.targetAudience}
                    </Tag>
                  </Space>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {templates.find(t => t.id === reportConfig.template)?.preview}
                  </Text>
                </div>
                <Form form={form} layout="vertical">
                  <Alert
                    message="输出格式"
                    description="点击「生成报告」按钮时选择输出格式"
                    type="info"
                    style={{ marginBottom: 16 }}
                  />

                  <Form.Item label="包含内容">
                    <Space direction="vertical">
                      <Checkbox
                        checked={reportConfig.includeCharts}
                        onChange={(e) => setReportConfig({...reportConfig, includeCharts: e.target.checked})}
                      >
                        包含图表和可视化
                      </Checkbox>
                      <Checkbox
                        checked={reportConfig.includeRawData}
                        onChange={(e) => setReportConfig({...reportConfig, includeRawData: e.target.checked})}
                      >
                        包含原始数据
                      </Checkbox>
                      <Checkbox
                        checked={reportConfig.includeModelComparison}
                        onChange={(e) => setReportConfig({...reportConfig, includeModelComparison: e.target.checked})}
                      >
                        包含模型对比分析
                      </Checkbox>
                      <Checkbox
                        checked={reportConfig.includeSummary}
                        onChange={(e) => setReportConfig({...reportConfig, includeSummary: e.target.checked})}
                      >
                        包含执行摘要
                      </Checkbox>
                    </Space>
                  </Form.Item>

                  <Form.Item label="自定义标题">
                    <Form.Item name="customTitle" noStyle>
                      <input
                        placeholder="可选：自定义报告标题"
                        value={reportConfig.customTitle || ''}
                        onChange={(e) => setReportConfig({...reportConfig, customTitle: e.target.value})}
                        style={{ width: '100%', padding: '4px 11px', border: '1px solid #d9d9d9', borderRadius: '6px' }}
                      />
                    </Form.Item>
                  </Form.Item>

                  <Form.Item label="报告描述">
                    <textarea
                      placeholder="可选：添加报告描述或说明"
                      value={reportConfig.customDescription || ''}
                      onChange={(e) => setReportConfig({...reportConfig, customDescription: e.target.value})}
                      rows={3}
                      style={{ width: '100%', padding: '4px 11px', border: '1px solid #d9d9d9', borderRadius: '6px' }}
                    />
                  </Form.Item>
                </Form>
              </Card>
            </Col>
          </Row>
        );

      case 2:
        return (
          <Card title="生成评测报告" size="small">
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Alert
                message="报告配置确认"
                description={
                  <div>
                    <Paragraph>
                      <strong>选中任务:</strong> {selectedTasks.length} 个
                    </Paragraph>
                    <Paragraph>
                      <strong>报告模板:</strong> {templates.find(t => t.id === reportConfig.template)?.name}
                    </Paragraph>
                    <Paragraph>
                      <strong>输出格式:</strong> 生成时选择
                    </Paragraph>
                    <Paragraph>
                      <strong>包含内容:</strong> 
                      {reportConfig.includeCharts && ' 图表'} 
                      {reportConfig.includeRawData && ' 原始数据'}
                      {reportConfig.includeModelComparison && ' 模型对比'}
                      {reportConfig.includeSummary && ' 执行摘要'}
                    </Paragraph>
                  </div>
                }
                type="info"
              />

              {generatingReport && (
                <div>
                  <Progress 
                    percent={33} 
                    status="active"
                    format={() => '正在生成报告...'}
                  />
                  <Text type="secondary" style={{ marginTop: 8, display: 'block' }}>
                    正在处理评测数据和生成可视化图表...
                  </Text>
                </div>
              )}

              <Space>
                <Button
                  type="primary"
                  size="large"
                  icon={<DownloadOutlined />}
                  loading={generatingReport}
                  onClick={handleGenerateReport}
                  disabled={selectedTasks.length === 0}
                >
                  {generatingReport ? '生成中...' : '生成报告'}
                </Button>
                <Button
                  size="large"
                  icon={<EyeOutlined />}
                  loading={loadingPreview}
                  onClick={handlePreviewReport}
                >
                  预览报告
                </Button>
                <Button
                  size="large"
                  icon={<ShareAltOutlined />}
                >
                  分享配置
                </Button>
              </Space>
            </Space>
          </Card>
        );

      default:
        return null;
    }
  };

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
              <BarChartOutlined /> 报告生成
            </Title>
          </Space>
        </Col>
      </Row>

      {/* 步骤条 */}
      <Card style={{ marginBottom: 24 }}>
        <Steps current={currentStep}>
          {steps.map((step, index) => (
            <Step
              key={index}
              title={step.title}
              description={step.description}
            />
          ))}
        </Steps>
      </Card>

      {/* 内容区域 */}
      {renderStepContent()}

      {/* 操作按钮 */}
      <div style={{ marginTop: 24, textAlign: 'center' }}>
        <Space>
          {currentStep > 0 && (
            <Button size="large" onClick={handlePrev}>
              上一步
            </Button>
          )}
          {currentStep < steps.length - 1 && (
            <Button 
              type="primary" 
              size="large"
              onClick={handleNext}
              disabled={currentStep === 0 && selectedTasks.length === 0}
            >
              下一步
            </Button>
          )}
        </Space>
      </div>

      {/* 格式选择Modal */}
      <Modal
        title="选择报告格式"
        open={formatModalVisible}
        onCancel={() => setFormatModalVisible(false)}
        onOk={handleConfirmGenerate}
        okText="生成报告"
        cancelText="取消"
        confirmLoading={generatingReport}
        width={600}
      >
        <div style={{ padding: '20px 0' }}>
          <Alert
            message="请选择报告输出格式"
            description="不同格式适合不同的使用场景"
            type="info"
            style={{ marginBottom: 24 }}
          />
          
          <Row gutter={16}>
            <Col span={12}>
              <Card
                hoverable
                style={{
                  border: selectedFormat === 'pdf' ? '2px solid #1890ff' : '1px solid #d9d9d9',
                  cursor: 'pointer',
                  backgroundColor: selectedFormat === 'pdf' ? '#f0f8ff' : '#fff'
                }}
                onClick={() => setSelectedFormat('pdf')}
              >
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <FileTextOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
                  <Title level={4} style={{ margin: '0 0 8px 0' }}>PDF 文档</Title>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    适合打印和分享，格式固定，兼容性好
                  </Text>
                  <div style={{ marginTop: 12 }}>
                    <Tag color="blue">推荐</Tag>
                    <Tag color="green">打印友好</Tag>
                  </div>
                </div>
              </Card>
            </Col>
            
            <Col span={12}>
              <Card
                hoverable
                style={{
                  border: selectedFormat === 'html' ? '2px solid #52c41a' : '1px solid #d9d9d9',
                  cursor: 'pointer',
                  backgroundColor: selectedFormat === 'html' ? '#f6ffed' : '#fff'
                }}
                onClick={() => setSelectedFormat('html')}
              >
                <div style={{ textAlign: 'center', padding: '20px' }}>
                  <FileTextOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
                  <Title level={4} style={{ margin: '0 0 8px 0' }}>HTML 网页</Title>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    可在浏览器中查看，支持交互，适合在线分享
                  </Text>
                  <div style={{ marginTop: 12 }}>
                    <Tag color="green">在线查看</Tag>
                    <Tag color="orange">交互友好</Tag>
                  </div>
                </div>
              </Card>
            </Col>
          </Row>
          
          <div style={{ marginTop: 24, padding: '16px', backgroundColor: '#f5f5f5', borderRadius: '6px' }}>
            <Text strong>格式对比：</Text>
            <div style={{ marginTop: 8 }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <strong>PDF:</strong> 适合正式报告、打印、邮件发送
                  </Text>
                </Col>
                <Col span={12}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    <strong>HTML:</strong> 适合在线查看、网页嵌入、交互展示
                  </Text>
                </Col>
              </Row>
            </div>
          </div>
        </div>
      </Modal>

      {/* 预览Modal */}
      <Modal
        title="报告预览"
        open={previewVisible}
        onCancel={() => {
          setPreviewVisible(false);
          setPreviewContent(null);
          setPreviewMode('simple');
        }}
        footer={null}
        width={previewMode === 'full' ? '90vw' : 1000}
        style={{ 
          top: 20,
          maxWidth: previewMode === 'full' ? '1400px' : '1000px'
        }}
        bodyStyle={{ 
          maxHeight: '80vh', 
          overflowY: 'auto',
          padding: previewContent?.html_content ? '12px' : '24px'
        }}
        centered={false}
        destroyOnClose={false}
      >
        {previewContent ? (
          <div>
            {/* 预览模式选择 */}
            <div style={{ marginBottom: 16, textAlign: 'center' }}>
              <Space>
                <Button 
                  type={previewMode === 'simple' ? "primary" : "default"}
                  size="small"
                  onClick={() => {
                    setPreviewMode('simple');
                  }}
                >
                  简化预览
                </Button>
                <Button 
                  type={previewMode === 'full' ? "primary" : "default"}
                  size="small"
                  onClick={() => {
                    setPreviewMode('full');
                    // 如果没有HTML内容，重新获取
                    if (!previewContent.html_content) {
                      handlePreviewReport();
                    }
                  }}
                >
                  完整预览
                </Button>
              </Space>
              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {previewMode === 'full' ? '显示与生成报告一致的完整内容' : '显示简化的预览内容'}
                </Text>
              </div>
            </div>

            {/* 完整HTML预览 */}
            {previewMode === 'full' && previewContent.html_content ? (
              <div 
                style={{ 
                  border: '1px solid #d9d9d9', 
                  borderRadius: '6px', 
                  overflow: 'auto',
                  backgroundColor: '#fff',
                  minHeight: '500px'
                }}
                dangerouslySetInnerHTML={{ __html: previewContent.html_content }}
              />
            ) : previewMode === 'simple' ? (
              /* 简化预览内容 */
              <div>
                {/* 报告标题 */}
                <div style={{ textAlign: 'center', marginBottom: 24 }}>
                  <Title level={3} style={{ color: '#1890ff' }}>
                    {previewContent.title}
                  </Title>
                  <Text type="secondary">
                    生成时间: {new Date().toLocaleString()}
                  </Text>
                </div>

                {/* 执行摘要 */}
                {reportConfig.includeSummary && (
                  <Card 
                    title={`${templates.find(t => t.id === reportConfig.template)?.name} - 摘要`} 
                    size="small" 
                    style={{ 
                      marginBottom: 16,
                      border: `2px solid ${templates.find(t => t.id === reportConfig.template)?.color || '#1890ff'}`
                    }}
                  >
                    <div style={{ 
                      backgroundColor: `${templates.find(t => t.id === reportConfig.template)?.color || '#1890ff'}08`,
                      padding: '12px',
                      borderRadius: '6px',
                      marginBottom: '12px'
                    }}>
                      <Space align="center">
                        <Text style={{ fontSize: 16 }}>
                          {templates.find(t => t.id === reportConfig.template)?.icon}
                        </Text>
                        <Text strong style={{ color: templates.find(t => t.id === reportConfig.template)?.color }}>
                          {templates.find(t => t.id === reportConfig.template)?.name}
                        </Text>
                        <Tag color={templates.find(t => t.id === reportConfig.template)?.color}>
                          {templates.find(t => t.id === reportConfig.template)?.targetAudience}
                        </Tag>
                      </Space>
                    </div>
                    <Paragraph style={{ whiteSpace: 'pre-line' }}>
                      {previewContent.summary}
                    </Paragraph>
                    {reportConfig.template === 'detailed' && (
                      <Alert
                        message="详细报告特色"
                        description="包含错误分析、模型对比、改进建议等深度分析内容"
                        type="info"
                        style={{ marginTop: 12 }}
                      />
                    )}
                    {reportConfig.template === 'executive' && (
                      <Alert
                        message="执行摘要特色"
                        description="突出关键指标、决策建议和风险提示，适合管理层参考"
                        type="warning"
                        style={{ marginTop: 12 }}
                      />
                    )}
                  </Card>
                )}

                {/* 任务详情 */}
                <Card title="评测任务详情" size="small">
                  {previewContent.tasks.map((task: any, index: number) => (
                    <Card
                      key={index}
                      size="small"
                      style={{ marginBottom: 12 }}
                      title={`${task.task_name} (${task.model_id})`}
                    >
                      <Row gutter={16}>
                        <Col span={12}>
                          <Space direction="vertical" size="small">
                            <div>
                              <Text strong>数据集: </Text>
                              <Text>{task.datasets.join(', ')}</Text>
                            </div>
                            <div>
                              <Text strong>状态: </Text>
                              <Tag color="green">{task.status}</Tag>
                            </div>
                            <div>
                              <Text strong>完成时间: </Text>
                              <Text>{task.completed_at ? new Date(task.completed_at).toLocaleString() : 'N/A'}</Text>
                            </div>
                          </Space>
                        </Col>
                        <Col span={12}>
                          <Space direction="vertical" size="small">
                            <div>
                              <Text strong>评测结果数: </Text>
                              <Text>{task.results_count}</Text>
                            </div>
                            <div>
                              <Text strong>报告格式: </Text>
                              <Tag color="blue">生成时选择</Tag>
                            </div>
                            <div>
                              <Text strong>报告模板: </Text>
                              <Text>{templates.find(t => t.id === reportConfig.template)?.name}</Text>
                            </div>
                          </Space>
                        </Col>
                      </Row>

                      {/* 结果预览 */}
                      {task.results && task.results.length > 0 && (
                        <div style={{ marginTop: 16 }}>
                          <Text strong>评测结果预览:</Text>
                          <Table
                            size="small"
                            dataSource={task.results}
                            columns={[
                              {
                                title: '数据集',
                                dataIndex: 'benchmark',
                                key: 'benchmark',
                                width: 120
                              },
                              {
                                title: '指标',
                                dataIndex: 'metric_name',
                                key: 'metric_name',
                                width: 120
                              },
                              {
                                title: '子集',
                                dataIndex: 'subset_name',
                                key: 'subset_name',
                                width: 100
                              },
                              {
                                title: '分数',
                                dataIndex: 'metric_value',
                                key: 'metric_value',
                                width: 80,
                                render: (value) => value ? value.toFixed(4) : 'N/A'
                              },
                              {
                                title: '样本数',
                                dataIndex: 'num_samples',
                                key: 'num_samples',
                                width: 80
                              }
                            ]}
                            pagination={false}
                            scroll={{ x: 500 }}
                          />
                          {task.results_count > 5 && (
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              显示前5个结果，完整报告将包含所有 {task.results_count} 个结果
                            </Text>
                          )}
                        </div>
                      )}
                    </Card>
                  ))}
                </Card>

                {/* 配置信息 */}
                <Card title="报告配置" size="small" style={{ marginTop: 16 }}>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Space direction="vertical" size="small">
                        <div>
                          <Text strong>包含内容: </Text>
                          <Space wrap>
                            {reportConfig.includeCharts && <Tag color="green">图表</Tag>}
                            {reportConfig.includeRawData && <Tag color="blue">原始数据</Tag>}
                            {reportConfig.includeModelComparison && <Tag color="orange">模型对比</Tag>}
                            {reportConfig.includeSummary && <Tag color="purple">执行摘要</Tag>}
                          </Space>
                        </div>
                      </Space>
                    </Col>
                    <Col span={12}>
                      <Space direction="vertical" size="small">
                        <div>
                          <Text strong>输出格式: </Text>
                          <Tag color="red">生成时选择</Tag>
                        </div>
                        <div>
                          <Text strong>报告模板: </Text>
                          <Text>{templates.find(t => t.id === reportConfig.template)?.name}</Text>
                        </div>
                      </Space>
                    </Col>
                  </Row>
                </Card>
              </div>
            ) : (
              /* 加载状态或其他情况 */
              <div style={{ textAlign: 'center', padding: '40px' }}>
                <Text type="secondary">请选择预览模式</Text>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <FileTextOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 16 }} />
            <Title level={4}>报告预览</Title>
            <Paragraph type="secondary">
              请先选择评测任务，然后点击预览按钮查看报告内容
            </Paragraph>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ReportGenerationPage;
