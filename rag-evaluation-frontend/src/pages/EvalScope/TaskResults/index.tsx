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
  Divider,
  Collapse,
  Tooltip
} from 'antd';
import {
  BarChartOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ArrowLeftOutlined,
  DownloadOutlined,
  EyeOutlined,
  EyeInvisibleOutlined
} from '@ant-design/icons';
import * as echarts from 'echarts';
import { evalscopeService } from '@/services/evalscope.service';
import { formatRunningTime, formatEffectiveDuration } from '../../../utils/timeFormat';
import type { EvalTask, EvalResult } from '@/types/evalscope.types';

// JSON报告数据结构
interface JsonReport {
  name: string;
  dataset_name: string;
  dataset_pretty_name: string;
  dataset_description: string;
  model_name: string;
  score: number;
  metrics: Array<{
    name: string;
    num: number;
    score: number;
    macro_score: number;
    categories: Array<{
      name: string | string[];
      num: number;
      score: number;
      macro_score: number;
      subsets: Array<{
        name: string;
        score: number;
        num: number;
      }>;
    }>;
  }>;
  analysis: string;
}

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
  const [jsonReports, setJsonReports] = useState<JsonReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDetailedScores, setShowDetailedScores] = useState(false);

  // 监听showDetailedScores变化，重新渲染图表
  useEffect(() => {
    if (jsonReports.length > 0) {
      setTimeout(() => renderChartsFromJson(jsonReports), 100);
    }
  }, [showDetailedScores, jsonReports]);

  // 从JSON报告转换为EvalResult格式
  const convertJsonToEvalResults = (jsonReport: JsonReport): EvalResult[] => {
    const evalResults: EvalResult[] = [];
    
    jsonReport.metrics.forEach(metric => {
      metric.categories.forEach(category => {
        // 处理category.name可能是数组的情况
        const categoryName = Array.isArray(category.name) ? category.name[0] : category.name;
        
        if (category.subsets && category.subsets.length > 0) {
          // 添加每个子集的结果
          category.subsets.forEach(subset => {
            evalResults.push({
              id: `${jsonReport.dataset_name}-${subset.name}`,
              task_id: parseInt(id || '0'),
              benchmark: jsonReport.dataset_name,
              metric_name: metric.name,
              metric_value: subset.score,
              category: categoryName,
              subset_name: subset.name,
              num_samples: subset.num,
              raw_results: { subset_data: subset },
              created_at: new Date().toISOString()
            });
          });
          
          // 添加类别平均分
          const totalSamples = category.subsets.reduce((sum, subset) => sum + subset.num, 0);
          const weightedScore = category.subsets.reduce((sum, subset) => sum + subset.score * subset.num, 0);
          const avgScore = totalSamples > 0 ? weightedScore / totalSamples : 0;
          
          evalResults.push({
            id: `${jsonReport.dataset_name}-${categoryName}-average`,
            task_id: parseInt(id || '0'),
            benchmark: jsonReport.dataset_name,
            metric_name: metric.name,
            metric_value: avgScore,
            category: categoryName,
            subset_name: 'average',
            num_samples: totalSamples,
            raw_results: { category_data: category },
            created_at: new Date().toISOString()
          });
        } else {
          // 如果没有子集，直接使用metric数据
          evalResults.push({
            id: `${jsonReport.dataset_name}-main`,
            task_id: parseInt(id || '0'),
            benchmark: jsonReport.dataset_name,
            metric_name: metric.name,
            metric_value: metric.score,
            category: categoryName,
            subset_name: 'main',
            num_samples: metric.num,
            raw_results: { metric_data: metric },
            created_at: new Date().toISOString()
          });
        }
      });
    });
    
    return evalResults;
  };

  // 从后端API获取JSON报告
  const loadJsonReports = async () => {
    try {
      setLoading(true);
      
      // 获取任务信息
      const taskData = await evalscopeService.getTask(parseInt(id || '0'));
      setTask(taskData);
      
      // 获取该任务的所有JSON报告
      const reports = await evalscopeService.getTaskJsonReports(parseInt(id || '0'));
      setJsonReports(reports);
      
      // 转换为EvalResult格式用于兼容现有代码
      const allResults: EvalResult[] = [];
      reports.forEach(report => {
        allResults.push(...convertJsonToEvalResults(report));
      });
      setResults(allResults);
      
    } catch (error) {
      console.error('加载JSON报告失败:', error);
    } finally {
      setLoading(false);
    }
  };

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
      loadJsonReports();
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
    // 渲染MMLU子集图表
    if (showDetailedScores) {
      renderCategoryChart(results);
      renderSubsetChart(results);
      renderHeatmapChart(results);
    }
  };

  // 从JSON报告渲染图表
  const renderChartsFromJson = (reports: JsonReport[]) => {
    // 转换为EvalResult格式用于图表渲染
    const allResults: EvalResult[] = [];
    reports.forEach(report => {
      allResults.push(...convertJsonToEvalResults(report));
    });
    
    renderRadarChart(allResults);
    renderBarChart(allResults);
    
    if (showDetailedScores) {
      renderCategoryChart(allResults);
      renderSubsetChart(allResults);
      renderHeatmapChart(allResults);
    }
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

  const renderCategoryChart = (results: EvalResult[]) => {
    const chartDom = document.getElementById('category-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);
    
    // 按类别分组计算平均分
    const categoryData: Record<string, { total: number; count: number; subsets: string[] }> = {};
    
    results.forEach(result => {
      if (result.subset_name !== 'average' && result.category) {
        if (!categoryData[result.category]) {
          categoryData[result.category] = { total: 0, count: 0, subsets: [] };
        }
        categoryData[result.category].total += result.metric_value || 0;
        categoryData[result.category].count += 1;
        categoryData[result.category].subsets.push(result.subset_name || '');
      }
    });

    const categories = Object.keys(categoryData);
    const scores = categories.map(cat => 
      categoryData[cat].count > 0 ? (categoryData[cat].total / categoryData[cat].count * 100) : 0
    );
    const subsetCounts = categories.map(cat => categoryData[cat].count);

    const option = {
      title: {
        text: '各类别平均得分',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const data = params[0];
          const category = categories[data.dataIndex];
          return `${category}<br/>平均得分: ${data.value.toFixed(2)}%<br/>子集数量: ${subsetCounts[data.dataIndex]}`;
        }
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisLabel: {
          rotate: 45
        }
      },
      yAxis: {
        type: 'value',
        name: '得分 (%)',
        min: 0,
        max: 100
      },
      series: [{
        name: '平均得分',
        type: 'bar',
        data: scores,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#ff9a9e' },
            { offset: 0.5, color: '#fecfef' },
            { offset: 1, color: '#fecfef' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#ff6b6b' },
              { offset: 0.7, color: '#ff8e8e' },
              { offset: 1, color: '#ff9a9e' }
            ])
          }
        }
      }]
    };

    myChart.setOption(option);
  };

  const renderSubsetChart = (results: EvalResult[]) => {
    const chartDom = document.getElementById('subset-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);
    
    // 获取所有子集得分（排除平均分）
    const subsetResults = results.filter(r => r.subset_name && r.subset_name !== 'average');
    
    // 按得分排序
    subsetResults.sort((a, b) => (b.metric_value || 0) - (a.metric_value || 0));
    
    // 取前20个子集显示
    const topSubsets = subsetResults.slice(0, 20);
    
    const subsetNames = topSubsets.map(r => {
      const name = r.subset_name || '';
      return name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    });
    const subsetScores = topSubsets.map(r => (r.metric_value || 0) * 100);

    const option = {
      title: {
        text: '子集得分排行 (Top 20)',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const data = params[0];
          return `${data.name}<br/>得分: ${data.value.toFixed(2)}%`;
        }
      },
      xAxis: {
        type: 'category',
        data: subsetNames,
        axisLabel: {
          rotate: 45,
          fontSize: 10
        }
      },
      yAxis: {
        type: 'value',
        name: '得分 (%)',
        min: 0,
        max: 100
      },
      series: [{
        name: '子集得分',
        type: 'bar',
        data: subsetScores,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#a8edea' },
            { offset: 0.5, color: '#fed6e3' },
            { offset: 1, color: '#fed6e3' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#74b9ff' },
              { offset: 0.7, color: '#a8edea' },
              { offset: 1, color: '#fed6e3' }
            ])
          }
        }
      }]
    };

    myChart.setOption(option);
  };

  const renderHeatmapChart = (results: EvalResult[]) => {
    const chartDom = document.getElementById('heatmap-chart');
    if (!chartDom) return;

    const myChart = echarts.init(chartDom);
    
    // 按类别和子集组织数据
    const categoryData: Record<string, Record<string, number>> = {};
    const allSubsets = new Set<string>();
    
    results.forEach(result => {
      if (result.subset_name && result.subset_name !== 'average' && result.category) {
        if (!categoryData[result.category]) {
          categoryData[result.category] = {};
        }
        categoryData[result.category][result.subset_name] = (result.metric_value || 0) * 100;
        allSubsets.add(result.subset_name);
      }
    });

    const categories = Object.keys(categoryData);
    const subsets = Array.from(allSubsets).sort();
    
    // 生成热力图数据
    const heatmapData: Array<[number, number, number]> = [];
    categories.forEach((category, catIndex) => {
      subsets.forEach((subset, subIndex) => {
        const score = categoryData[category][subset] || 0;
        heatmapData.push([subIndex, catIndex, score]);
      });
    });

    const option = {
      title: {
        text: '子集得分热力图',
        left: 'center'
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const subset = subsets[params.data[0]];
          const category = categories[params.data[1]];
          const score = params.data[2];
          return `${category}<br/>${subset}<br/>得分: ${score.toFixed(2)}%`;
        }
      },
      grid: {
        height: '50%',
        top: '10%'
      },
      xAxis: {
        type: 'category',
        data: subsets.map(s => s.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())),
        splitArea: {
          show: true
        },
        axisLabel: {
          rotate: 45,
          fontSize: 10
        }
      },
      yAxis: {
        type: 'category',
        data: categories,
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
        bottom: '15%',
        inRange: {
          color: ['#50a3ba', '#eac736', '#d94e5d']
        }
      },
      series: [{
        name: '得分',
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: true,
          formatter: (params: any) => {
            return params.data[2].toFixed(0) + '%';
          }
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

  // 按benchmark分组结果，区分平均分和子集得分
  const groupResultsByBenchmark = () => {
    const grouped: Record<string, { 
      average: EvalResult | null; 
      subsets: EvalResult[];
      categories: Record<string, EvalResult[]>;
    }> = {};
    
    results.forEach(result => {
      const benchmark = result.benchmark;
      if (!grouped[benchmark]) {
        grouped[benchmark] = { 
          average: null, 
          subsets: [],
          categories: {}
        };
      }
      
      if (result.subset_name === 'average') {
        grouped[benchmark].average = result;
      } else if (result.subset_name) {
        // 包含所有子集，包括 'main'
        grouped[benchmark].subsets.push(result);
        
        // 按类别分组
        const category = result.category || 'default';
        if (!grouped[benchmark].categories[category]) {
          grouped[benchmark].categories[category] = [];
        }
        grouped[benchmark].categories[category].push(result);
      }
    });
    
    return grouped;
  };

  // 从JSON报告分组数据
  const groupJsonReportsByBenchmark = () => {
    const grouped: Record<string, { 
      report: JsonReport;
      average: EvalResult | null; 
      subsets: EvalResult[];
      categories: Record<string, EvalResult[]>;
    }> = {};
    
    jsonReports.forEach(report => {
      const benchmark = report.dataset_name;
      const evalResults = convertJsonToEvalResults(report);
      
      grouped[benchmark] = { 
        report,
        average: null, 
        subsets: [],
        categories: {}
      };
      
      evalResults.forEach(result => {
        if (result.subset_name === 'average') {
          grouped[benchmark].average = result;
        } else if (result.subset_name) {
          // 包含所有子集，包括 'main'
          grouped[benchmark].subsets.push(result);
          
          // 按类别分组
          const category = result.category || 'default';
          if (!grouped[benchmark].categories[category]) {
            grouped[benchmark].categories[category] = [];
          }
          grouped[benchmark].categories[category].push(result);
        }
      });
    });
    
    return grouped;
  };


  // 获取子集得分的统计信息
  const getSubsetStats = (subsets: EvalResult[]) => {
    if (subsets.length === 0) return null;
    
    const scores = subsets.map(s => s.metric_value || 0);
    const best = Math.max(...scores);
    const worst = Math.min(...scores);
    const avg = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    
    return { best, worst, avg, count: subsets.length };
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
  
  // 优先使用有效执行时长（排除暂停时间），否则使用传统计算方式
  const duration = task.effective_duration 
    ? formatEffectiveDuration(task.effective_duration)
    : (task.started_at && task.completed_at 
        ? formatRunningTime(task.started_at, task.completed_at)
        : 'N/A');

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
            <Button 
              icon={showDetailedScores ? <EyeInvisibleOutlined /> : <EyeOutlined />}
              onClick={() => setShowDetailedScores(!showDetailedScores)}
            >
              {showDetailedScores ? '隐藏子集得分' : '显示子集得分'}
            </Button>
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

      {/* MMLU子集得分可视化 */}
      {showDetailedScores && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={24}>
            <Card title="MMLU子集得分可视化">
              <Row gutter={16}>
                <Col span={12}>
                  <Card size="small" title="按类别分组得分">
                    <div id="category-chart" style={{ width: '100%', height: '300px' }}></div>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small" title="子集得分分布">
                    <div id="subset-chart" style={{ width: '100%', height: '300px' }}></div>
                  </Card>
                </Col>
              </Row>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={24}>
                  <Card size="small" title="子集得分热力图">
                    <div id="heatmap-chart" style={{ width: '100%', height: '400px' }}></div>
                  </Card>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>
      )}

      {/* 详细结果表格 */}
      <Card title="详细评测结果">
        {showDetailedScores ? (
          <div>
            {/* 优化后的折叠面板视图 */}
            <Collapse 
              defaultActiveKey={[]}
              items={Object.entries(groupJsonReportsByBenchmark()).map(([benchmark, data]) => {
                const subsetStats = getSubsetStats(data.subsets);
                const hasSubsets = data.subsets.length > 0;
                
                return {
                  key: benchmark,
                  label: (
                    <Space>
                      <Tag color="blue">{benchmark.toUpperCase()}</Tag>
                      {data.average && (
                        <Space>
                          <Text strong>总体得分: {(data.average.metric_value! * 100).toFixed(2)}%</Text>
                          <Text type="secondary">({data.average.num_samples} 样本)</Text>
                        </Space>
                      )}
                      {hasSubsets && subsetStats && (
                        <Space>
                          <Text type="secondary">
                            {subsetStats.count}个子集 | 
                            平均: {(subsetStats.avg * 100).toFixed(1)}% | 
                            最佳: {(subsetStats.best * 100).toFixed(1)}% | 
                            最差: {(subsetStats.worst * 100).toFixed(1)}%
                          </Text>
                        </Space>
                      )}
                    </Space>
                  ),
                  children: (
                    <div>
                      {/* 总体信息显示 */}
                      {data.average && (
                        <Card size="small" style={{ marginBottom: 16, backgroundColor: '#fff7e6' }}>
                          <Row gutter={16}>
                            <Col span={6}>
                              <Statistic
                                title="总体得分"
                                value={(data.average.metric_value! * 100).toFixed(2)}
                                suffix="%"
                                valueStyle={{ color: '#fa8c16' }}
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="总样本数"
                                value={data.average.num_samples || 0}
                                valueStyle={{ color: '#1890ff' }}
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="评测指标"
                                value={data.average.metric_name}
                                valueStyle={{ color: '#52c41a' }}
                              />
                            </Col>
                            <Col span={6}>
                              <Statistic
                                title="类别数量"
                                value={Object.keys(data.categories).length}
                                valueStyle={{ color: '#722ed1' }}
                              />
                            </Col>
                          </Row>
                        </Card>
                      )}
                      
                              {/* 按类别分组的子集得分 */}
                              {hasSubsets && (
                                <div>
                                  <Collapse 
                                    size="small"
                                    items={Object.entries(data.categories).map(([categoryName, categorySubsets]) => {
                                      const categoryStats = getSubsetStats(categorySubsets);
                                      return {
                                        key: categoryName,
                                        label: (
                                          <Space>
                                            <Tag color="purple">{categoryName}</Tag>
                                            <Text strong>类别得分: {(categoryStats?.avg * 100).toFixed(2)}%</Text>
                                            <Text type="secondary">
                                              ({categorySubsets.length}个子集 | 
                                              最佳: {(categoryStats?.best * 100).toFixed(1)}% | 
                                              最差: {(categoryStats?.worst * 100).toFixed(1)}%)
                                            </Text>
                                          </Space>
                                        ),
                                        children: (
                                          <Table
                                            columns={[
                                              {
                                                title: '子集名称',
                                                dataIndex: 'subset_name',
                                                key: 'subset_name',
                                                width: '40%',
                                                render: (name: string) => {
                                                  // 显示原始名称和美化名称
                                                  const displayName = name
                                                    .replace(/_/g, ' ')
                                                    .replace(/\b\w/g, l => l.toUpperCase());
                                                  return (
                                                    <Space direction="vertical" size={0}>
                                                      <Tag color="cyan">{name}</Tag>
                                                      <Text type="secondary" style={{ fontSize: '12px' }}>
                                                        {displayName}
                                                      </Text>
                                                    </Space>
                                                  );
                                                }
                                              },
                                              {
                                                title: '得分',
                                                dataIndex: 'metric_value',
                                                key: 'metric_value',
                                                width: '30%',
                                                render: (value: number) => (
                                                  <Space direction="vertical" size={0}>
                                                    <Text strong style={{ fontSize: '16px' }}>
                                                      {value ? (value * 100).toFixed(2) : '0.00'}%
                                                    </Text>
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
                                                width: '15%',
                                                render: (num: number) => (
                                                  <Text strong style={{ fontSize: '14px' }}>
                                                    {num || 'N/A'}
                                                  </Text>
                                                )
                                              },
                                              {
                                                title: '类别',
                                                dataIndex: 'category',
                                                key: 'category',
                                                width: '15%',
                                                render: (category: string) => (
                                                  <Tag color="purple" style={{ fontSize: '12px' }}>
                                                    {category}
                                                  </Tag>
                                                )
                                              }
                                            ]}
                                            dataSource={categorySubsets}
                                            rowKey={(record) => `${record.benchmark}-${record.subset_name}`}
                                            pagination={false}
                                            size="small"
                                            bordered
                                          />
                                        )
                                      };
                                    })}
                                  />
                                </div>
                              )}
                    </div>
                  )
                };
              })}
            />
          </div>
        ) : (
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
        )}
      </Card>
    </div>
  );
};

export default TaskResults;


