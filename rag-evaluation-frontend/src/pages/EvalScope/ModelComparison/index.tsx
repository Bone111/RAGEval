import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Select,
  Space,
  Typography,
  Row,
  Col,
  Tag,
  Progress,
  Alert,
  Divider,
  Statistic,
  Tooltip,
  Empty,
  Spin,
  message,
  Modal,
  Descriptions
} from 'antd';
import {
  SwapOutlined,
  TrophyOutlined,
  BarChartOutlined,
  DotChartOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  ArrowLeftOutlined,
  InfoCircleOutlined,
  DownloadOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { evalscopeService } from '@/services/evalscope.service';
import type { 
  ComparisonResponse, 
  ComparisonTask, 
  ComparisonAnalysis,
  ComparisonStatistics,
  ComparisonCharts,
  ComparisonRequest
} from '@/types/evalscope.types';

const { Title, Text } = Typography;
const { Option } = Select;

const ModelComparison: React.FC = () => {
  const navigate = useNavigate();
  const [availableTasks, setAvailableTasks] = useState<ComparisonTask[]>([]);
  const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([]);
  const [comparisonResponse, setComparisonResponse] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [comparisonType, setComparisonType] = useState<'detailed' | 'summary' | 'report'>('detailed');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeStatistics, setIncludeStatistics] = useState(true);
  const [statisticsModalVisible, setStatisticsModalVisible] = useState(false);

  useEffect(() => {
    loadAvailableTasks();
  }, []);

  useEffect(() => {
    if (comparisonResponse && includeCharts) {
      setTimeout(() => {
        renderComparisonCharts();
      }, 100);
    }
  }, [comparisonResponse, includeCharts]);

  const loadAvailableTasks = async () => {
    try {
      const response = await evalscopeService.getCompletedTasksForComparison();
      setAvailableTasks(response.tasks || []);
    } catch (error) {
      console.error('加载已完成任务失败:', error);
      message.error('加载任务列表失败');
    }
  };

  const handleCompare = async () => {
    if (selectedTaskIds.length < 2) {
      message.warning('请至少选择2个任务进行对比');
      return;
    }

    if (selectedTaskIds.length > 10) {
      message.warning('最多支持10个任务对比');
      return;
    }

    setLoading(true);
    try {
      const request: ComparisonRequest = {
        task_ids: selectedTaskIds,
        comparison_type: comparisonType,
        include_charts: includeCharts,
        include_statistics: includeStatistics
      };

      const response = await evalscopeService.compareModels(request);
      setComparisonResponse(response);
      message.success('模型对比分析完成');
    } catch (error) {
      console.error('对比分析失败:', error);
      message.error('对比分析失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleExportReport = async () => {
    if (!comparisonResponse) {
      message.warning('请先进行对比分析');
      return;
    }

    try {
      const request: ComparisonRequest = {
        task_ids: selectedTaskIds,
        comparison_type: 'report',
        include_charts: true,
        include_statistics: true
      };

      const blob = await evalscopeService.exportComparisonReport(request);
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `模型对比报告_${comparisonResponse.comparison_id}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      message.success('报告导出成功');
    } catch (error) {
      console.error('导出报告失败:', error);
      message.error('导出报告失败，请重试');
    }
  };

  const renderComparisonCharts = () => {
    if (!comparisonResponse?.charts_data) return;
    
    renderRadarComparison();
    renderBarComparison();
    renderScoreHeatmap();
  };

  const renderRadarComparison = () => {
    const chartDom = document.getElementById('radar-comparison');
    if (!chartDom || !comparisonResponse?.charts_data) return;

    const myChart = echarts.init(chartDom);
    const { radar } = comparisonResponse.charts_data;

    const option = {
      title: {
        text: '模型能力雷达对比',
        left: 'center'
      },
      tooltip: {
        trigger: 'item'
      },
      legend: {
        data: radar.series.map(s => s.name),
        bottom: 10
      },
      radar: {
        indicator: radar.indicators,
        name: {
          textStyle: {
            color: '#666'
          }
        }
      },
      series: [{
        name: '模型对比',
        type: 'radar',
        data: radar.series,
        areaStyle: {
          opacity: 0.3
        }
      }]
    };

    myChart.setOption(option);
  };

  const renderBarComparison = () => {
    const chartDom = document.getElementById('bar-comparison');
    if (!chartDom || !comparisonResponse?.charts_data) return;

    const myChart = echarts.init(chartDom);
    const { bar } = comparisonResponse.charts_data;

    const series = bar.data.map((item, index) => ({
      name: item.dataset,
      type: 'bar',
      data: item.scores,
      itemStyle: {
        color: `hsl(${index * 60}, 70%, 50%)`
      }
    }));

    const option = {
      title: {
        text: '各数据集详细对比',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      legend: {
        data: bar.datasets,
        bottom: 10
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: bar.data[0]?.models || [],
        axisLabel: {
          rotate: 45
        }
      },
      yAxis: {
        type: 'value',
        name: '分数 (%)'
      },
      series: series
    };

    myChart.setOption(option);
  };

  const renderScoreHeatmap = () => {
    const chartDom = document.getElementById('heatmap-comparison');
    if (!chartDom || !comparisonResponse?.charts_data) return;

    const myChart = echarts.init(chartDom);
    const { heatmap } = comparisonResponse.charts_data;

    const option = {
      title: {
        text: '模型-数据集热力图',
        left: 'center'
      },
      tooltip: {
        position: 'top',
        formatter: function (params: any) {
          return `${heatmap.xAxis[params.data[0]]}<br/>${heatmap.yAxis[params.data[1]]}<br/>分数: ${params.data[2].toFixed(2)}%`;
        }
      },
      grid: {
        height: '50%',
        top: '10%'
      },
      xAxis: {
        type: 'category',
        data: heatmap.xAxis.map(d => d.toUpperCase()),
        splitArea: {
          show: true
        }
      },
      yAxis: {
        type: 'category',
        data: heatmap.yAxis,
        splitArea: {
          show: true
        }
      },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '5%',
        inRange: {
          color: ['#50a3ba', '#eac736', '#d94e5d']
        }
      },
      series: [{
        name: '分数',
        type: 'heatmap',
        data: heatmap.data,
        label: {
          show: true,
          formatter: '{c}%'
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    };

    myChart.setOption(option);
  };

  const generateComparisonTable = () => {
    if (!comparisonResponse?.comparison_data) return [];

    return comparisonResponse.comparison_data.comparison_table;
  };

  const tableColumns = [
    {
      title: 'Benchmark',
      dataIndex: 'benchmark',
      key: 'benchmark',
      render: (text: string) => <Tag color="blue">{text.toUpperCase()}</Tag>
    },
    ...(comparisonResponse?.comparison_data?.models || []).map(modelId => ({
      title: modelId,
      dataIndex: modelId,
      key: modelId,
      render: (score: number | null) => {
        if (score === null) return <Text type="secondary">-</Text>;
        return (
          <Space>
            <Text strong>{score.toFixed(2)}%</Text>
            <Progress 
              percent={score} 
              size="small" 
              showInfo={false}
              strokeColor={score > 80 ? '#52c41a' : score > 60 ? '#faad14' : '#ff4d4f'}
            />
          </Space>
        );
      }
    }))
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* 标题和返回按钮 */}
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
              <SwapOutlined /> 模型对比分析
            </Title>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button 
              icon={<InfoCircleOutlined />}
              onClick={() => setStatisticsModalVisible(true)}
              disabled={!comparisonResponse}
            >
              统计信息
            </Button>
            <Button 
              icon={<DownloadOutlined />}
              onClick={handleExportReport}
              disabled={!comparisonResponse}
            >
              导出报告
            </Button>
            <Button 
              icon={<ReloadOutlined />}
              onClick={loadAvailableTasks}
            >
              刷新任务
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 任务选择器 */}
      <Card title="选择对比任务" style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col span={12}>
            <Select
              mode="multiple"
              placeholder="请选择要对比的已完成任务（至少2个）"
              value={selectedTaskIds}
              onChange={setSelectedTaskIds}
              style={{ width: '100%' }}
              showSearch
              optionFilterProp="children"
            >
              {availableTasks.map(task => (
                <Option key={task.task_id} value={task.task_id}>
                  <Space>
                    <Text strong>{task.task_name}</Text>
                    <Tag color="green">{task.model_id}</Tag>
                    <Text type="secondary">
                      {task.datasets.join(', ')}
                    </Text>
                  </Space>
                </Option>
              ))}
            </Select>
          </Col>
          <Col span={4}>
            <Select
              value={comparisonType}
              onChange={setComparisonType}
              style={{ width: '100%' }}
            >
              <Option value="detailed">详细对比</Option>
              <Option value="summary">摘要对比</Option>
              <Option value="report">报告对比</Option>
            </Select>
          </Col>
          <Col span={4}>
            <Space>
              <label>
                <input 
                  type="checkbox" 
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts(e.target.checked)}
                />
                图表
              </label>
              <label>
                <input 
                  type="checkbox" 
                  checked={includeStatistics}
                  onChange={(e) => setIncludeStatistics(e.target.checked)}
                />
                统计
              </label>
            </Space>
          </Col>
          <Col span={4}>
            <Button
              type="primary"
              icon={<SwapOutlined />}
              onClick={handleCompare}
              loading={loading}
              disabled={selectedTaskIds.length < 2}
            >
              开始对比分析
            </Button>
          </Col>
        </Row>
      </Card>

      {!comparisonResponse ? (
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="请选择任务开始对比分析"
          />
        </Card>
      ) : (
        <Spin spinning={loading}>
          {/* 关键指标 */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            {comparisonResponse.tasks.map((task, index) => (
              <Col span={24 / comparisonResponse.tasks.length} key={task.task_id}>
                <Card>
                  <Statistic
                    title={
                      <Space>
                        <TrophyOutlined />
                        {task.model_id}
                      </Space>
                    }
                    value={comparisonResponse.comparison_data.win_rates[task.model_id] || 0}
                    suffix="%"
                    valueStyle={{ 
                      color: index === 0 ? '#3f8600' : index === 1 ? '#1890ff' : '#722ed1' 
                    }}
                  />
                  <Text type="secondary" style={{ fontSize: '12px' }}>
                    胜率 (vs 其他模型)
                  </Text>
                  <Divider style={{ margin: '8px 0' }} />
                  <Statistic
                    title="平均分数"
                    value={comparisonResponse.comparison_data.average_scores[task.model_id] || 0}
                    suffix="%"
                    valueStyle={{ fontSize: '16px' }}
                  />
                </Card>
              </Col>
            ))}
          </Row>

          {/* 可视化图表 */}
          {includeCharts && (
            <>
              <Row gutter={16} style={{ marginBottom: 24 }}>
                <Col span={12}>
                  <Card title={<Space><DotChartOutlined />雷达图对比</Space>}>
                    <div id="radar-comparison" style={{ width: '100%', height: '400px' }}></div>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title={<Space><BarChartOutlined />柱状图对比</Space>}>
                    <div id="bar-comparison" style={{ width: '100%', height: '400px' }}></div>
                  </Card>
                </Col>
              </Row>

              {/* 热力图 */}
              <Card title="评分热力图" style={{ marginBottom: 24 }}>
                <div id="heatmap-comparison" style={{ width: '100%', height: '300px' }}></div>
              </Card>
            </>
          )}

          {/* 详细对比表格 */}
          <Card title="详细分数对比">
            <Table
              columns={tableColumns}
              dataSource={generateComparisonTable()}
              pagination={false}
              rowKey="benchmark"
              size="middle"
            />
          </Card>
        </Spin>
      )}

      {/* 统计信息模态框 */}
      <Modal
        title="对比分析统计信息"
        open={statisticsModalVisible}
        onCancel={() => setStatisticsModalVisible(false)}
        footer={null}
        width={800}
      >
        {comparisonResponse?.statistics && (
          <Descriptions bordered column={2}>
            <Descriptions.Item label="对比ID" span={2}>
              {comparisonResponse.comparison_id}
            </Descriptions.Item>
            <Descriptions.Item label="生成时间" span={2}>
              {new Date(comparisonResponse.generated_at).toLocaleString()}
            </Descriptions.Item>
            <Descriptions.Item label="参与模型数">
              {comparisonResponse.tasks.length}
            </Descriptions.Item>
            <Descriptions.Item label="数据集数">
              {comparisonResponse.comparison_data.datasets.length}
            </Descriptions.Item>
            {comparisonResponse.statistics.global_statistics.best_model && (
              <Descriptions.Item label="最佳模型" span={2}>
                <Space>
                  <Tag color="green">{comparisonResponse.statistics.global_statistics.best_model.model_id}</Tag>
                  <Text>平均分数: {(comparisonResponse.statistics.global_statistics.best_model.average_score * 100).toFixed(2)}%</Text>
                </Space>
              </Descriptions.Item>
            )}
            {comparisonResponse.statistics.global_statistics.worst_model && (
              <Descriptions.Item label="最差模型" span={2}>
                <Space>
                  <Tag color="red">{comparisonResponse.statistics.global_statistics.worst_model.model_id}</Tag>
                  <Text>平均分数: {(comparisonResponse.statistics.global_statistics.worst_model.average_score * 100).toFixed(2)}%</Text>
                </Space>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default ModelComparison;
