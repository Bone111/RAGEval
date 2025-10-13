import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Tag,
  Statistic,
  Row,
  Col,
  Alert,
  Spin,
  Typography,
  Progress,
  Space,
  Descriptions,
  Divider
} from 'antd';
import {
  BarChartOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ArrowLeftOutlined,
  DownloadOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { evalscopeService } from '@/services/evalscope.service';
import { formatRunningTime } from '../../../utils/timeFormat';
import type { EvalTask, EvalResult } from '@/types/evalscope.types';

const { Title, Text } = Typography;

// 添加样式
const tableStyles = `
  .average-row {
    background-color: #fff7e6 !important;
    font-weight: 500;
  }
  .average-row:hover {
    background-color: #fff2d9 !important;
  }
`;

const TaskResults: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<EvalTask | null>(null);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [loading, setLoading] = useState(true);

  // 跳转到报告生成页面
  const handleExportReport = () => {
    navigate('/evalscope/reports');
  };

  // 跳转到报告生成页面（生成分析报告）
  const handleGenerateReport = () => {
    navigate('/evalscope/reports');
  };

  useEffect(() => {
    if (id) {
      loadTaskAndResults();
    }
  }, [id]);

  const loadTaskAndResults = async () => {
    try {
      setLoading(true);
      const [taskData, resultsData] = await Promise.all([
        evalscopeService.getTask(parseInt(id!)),
        evalscopeService.getTaskResults(parseInt(id!))
      ]);
      setTask(taskData);
      setResults(resultsData);
      
      // 如果有结果，渲染图表
      if (resultsData.length > 0) {
        setTimeout(() => renderCharts(resultsData), 100);
      }
    } catch (error) {
      console.error('加载任务结果失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const renderCharts = (results: EvalResult[]) => {
    // 渲染雷达图
    renderRadarChart(results);
    // 渲染柱状图
    renderBarChart(results);
  };

  const renderRadarChart = (results: EvalResult[]) => {
    const chartDom = document.getElementById('radar-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);
    
    // 准备雷达图数据
    const indicators = results.map(result => ({
      name: result.benchmark,
      max: 100
    }));

    const data = [{
      value: results.map(result => (result.metric_value || 0) * 100),
      name: task?.model_id || 'Model'
    }];

    const option = {
      title: {
        text: '评测结果雷达图',
        left: 'center'
      },
      tooltip: {},
      radar: {
        indicator: indicators,
        name: {
          textStyle: {
            color: '#666'
          }
        }
      },
      series: [{
        name: '评测分数',
        type: 'radar',
        data: data,
        areaStyle: {
          opacity: 0.3
        },
        itemStyle: {
          color: '#1890ff'
        }
      }]
    };

    myChart.setOption(option);
  };

  const renderBarChart = (results: EvalResult[]) => {
    const chartDom = document.getElementById('bar-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);

    const option = {
      title: {
        text: '各数据集评测分数',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const data = params[0];
          return `${data.name}<br/>${data.seriesName}: ${data.value.toFixed(2)}%`;
        }
      },
      xAxis: {
        type: 'category',
        data: results.map(r => r.benchmark),
        axisLabel: {
          rotate: 45
        }
      },
      yAxis: {
        type: 'value',
        name: '分数 (%)',
        min: 0,
        max: 100
      },
      series: [{
        name: '评测分数',
        type: 'bar',
        data: results.map(r => ((r.metric_value || 0) * 100)),
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#83bff6' },
            { offset: 0.5, color: '#188df0' },
            { offset: 1, color: '#188df0' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#2378f7' },
              { offset: 0.7, color: '#2378f7' },
              { offset: 1, color: '#83bff6' }
            ])
          }
        }
      }]
    };

    myChart.setOption(option);
  };

  const getStatusColor = (status: string) => {
    const colors = {
      pending: 'orange',
      running: 'blue',
      completed: 'green',
      failed: 'red',
      cancelled: 'gray'
    };
    return colors[status as keyof typeof colors] || 'gray';
  };

  const calculateAverageScore = () => {
    if (results.length === 0) return 0;
    const sum = results.reduce((acc, result) => acc + (result.metric_value || 0), 0);
    return (sum / results.length * 100).toFixed(1);
  };

  const getBestPerformance = () => {
    if (results.length === 0) return null;
    return results.reduce((best, current) => 
      (current.metric_value || 0) > (best.metric_value || 0) ? current : best
    );
  };

  const columns = [
    {
      title: 'Benchmark',
      dataIndex: 'benchmark',
      key: 'benchmark',
      render: (text: string) => <Tag color="blue">{text.toUpperCase()}</Tag>
    },
    {
      title: '子集',
      dataIndex: 'subset_name',
      key: 'subset_name',
      render: (subset: string) => {
        if (!subset) return <Text type="secondary">-</Text>;
        
        // 特殊处理平均分
        if (subset === 'average') {
          return <Tag color="gold">平均分</Tag>;
        }
        
        // 处理多个子集合并的情况（兼容旧数据）
        if (subset.includes('+')) {
          const subsets = subset.split('+');
          return (
            <Space wrap>
              {subsets.map((s, index) => (
                <Tag key={index} color="cyan">{s}</Tag>
              ))}
            </Space>
          );
        }
        
        // 单个子集
        return <Tag color="cyan">{subset}</Tag>;
      }
    },
    {
      title: '指标',
      dataIndex: 'metric_name',
      key: 'metric_name'
    },
    {
      title: '分数',
      dataIndex: 'metric_value',
      key: 'metric_value',
      render: (value: number) => (
        <Space>
          <Text strong>{value ? (value * 100).toFixed(2) : '0.00'}%</Text>
          <Progress 
            percent={value ? value * 100 : 0} 
            size="small" 
            showInfo={false}
            strokeColor={value > 0.8 ? '#52c41a' : value > 0.5 ? '#faad14' : '#ff4d4f'}
          />
        </Space>
      )
    },
    {
      title: '样本数',
      dataIndex: 'num_samples',
      key: 'num_samples',
      render: (num: number) => <Text type="secondary">{num || 'N/A'}</Text>
    },
    {
      title: '类别',
      dataIndex: 'category',
      key: 'category',
      render: (category: string) => <Tag>{category || 'default'}</Tag>
    }
  ];

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Spin size="large" tip="加载结果中..." />
      </div>
    );
  }

  if (!task) {
    return (
      <Card>
        <Alert message="任务不存在" type="error" />
      </Card>
    );
  }

  const bestResult = getBestPerformance();
  const duration = task.started_at && task.completed_at 
    ? formatRunningTime(task.started_at, task.completed_at)
    : 'N/A';

  return (
    <div style={{ padding: '24px' }}>
      <style>{tableStyles}</style>
      {/* 标题和操作栏 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
          <Space>
            <Button 
              icon={<ArrowLeftOutlined />} 
              onClick={() => navigate('/evalscope/tasks')}
            >
              返回任务列表
            </Button>
            <Title level={2} style={{ margin: 0 }}>
              评测结果详情
            </Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button icon={<DownloadOutlined />} onClick={handleExportReport}>导出报告</Button>
            <Button type="primary" icon={<BarChartOutlined />} onClick={handleGenerateReport}>
              生成分析报告
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 任务基本信息 */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions title="任务信息" bordered column={3}>
          <Descriptions.Item label="任务名称">{task.task_name}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={getStatusColor(task.status)}>{task.status.toUpperCase()}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="模型">{task.model_id}</Descriptions.Item>
          <Descriptions.Item label="数据集">
            <Space>
              {task.datasets.map(dataset => (
                <Tag color="cyan" key={dataset}>{dataset}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="执行时长">
            <Space>
              <ClockCircleOutlined />
              {duration}
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(task.created_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 关键指标 */}
      {results.length > 0 ? (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="平均分数"
                value={calculateAverageScore()}
                suffix="%"
                valueStyle={{ color: '#3f8600' }}
                prefix={<TrophyOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="最佳表现"
                value={bestResult ? (bestResult.metric_value! * 100).toFixed(1) : '0'}
                suffix="%"
                valueStyle={{ color: '#cf1322' }}
                prefix={<DatabaseOutlined />}
              />
              {bestResult && (
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  {bestResult.benchmark} {bestResult.subset_name && bestResult.subset_name !== 'average' ? `(${bestResult.subset_name})` : ''}
                </Text>
              )}
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="评测数据集"
                value={results.length}
                suffix="个"
                valueStyle={{ color: '#1890ff' }}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总样本数"
                value={results.reduce((sum, r) => sum + (r.num_samples || 0), 0)}
                valueStyle={{ color: '#722ed1' }}
              />
            </Card>
          </Col>
        </Row>
      ) : (
        <Alert
          message="暂无评测结果"
          description="该任务尚未产生评测结果，可能仍在执行中或执行失败。"
          type="warning" 
          style={{ marginBottom: 24 }}
        />
      )}

      {/* 图表区域 */}
      {results.length > 0 && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={12}>
            <Card title="雷达图分析">
              <div id="radar-chart" style={{ width: '100%', height: '300px' }}></div>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="柱状图对比">
              <div id="bar-chart" style={{ width: '100%', height: '300px' }}></div>
            </Card>
          </Col>
        </Row>
      )}

      {/* 详细结果表格 */}
      <Card title="详细评测结果">
        <Table
          columns={columns}
          dataSource={results}
          rowKey={(record) => `${record.benchmark}-${record.metric_name}-${record.subset_name}`}
          pagination={false}
          size="middle"
          rowClassName={(record) => {
            // 为平均分添加特殊样式
            if (record.subset_name === 'average') {
              return 'average-row';
            }
            return '';
          }}
        />
      </Card>
    </div>
  );
};

export default TaskResults;


