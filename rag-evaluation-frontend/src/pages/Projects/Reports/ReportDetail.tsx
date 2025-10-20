import React, { useState, useEffect } from 'react';
import {
  Layout, Typography, Button, Card, Row, Col, Statistic,
  Tag, Space, Spin, message, Empty
} from 'antd';
import {
  ArrowLeftOutlined, DownloadOutlined,
  BarChartOutlined, ReloadOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { reportService, Report } from '../../../services/report.service';
import ReportCharts from '../../../components/ReportCharts';

const { Title, Text, Paragraph } = Typography;

const ReportDetailPage: React.FC = () => {
  const { projectId, reportId } = useParams<{ projectId: string; reportId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (reportId) {
      fetchReport();
    }
  }, [reportId]);

  const fetchReport = async (forceRefresh = false) => {
    setLoading(true);
    try {
      const data = await reportService.getReport(reportId!, forceRefresh || false);
      setReport(data);
      if (forceRefresh) {
        message.success('报告内容已更新');
      }
    } catch (error) {
      console.error('获取报告详情失败:', error);
      message.error('获取报告详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshReport = () => {
    fetchReport(true);
  };

  const handleExportReport = async () => {
    if (!report) return;
    try {
      // 生成Markdown格式的报告
      const markdownContent = generateMarkdownReport(report);
      
      // 创建下载链接
      const blob = new Blob([markdownContent], {
        type: 'text/markdown;charset=utf-8'
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${report.title}_报告.md`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      message.success('Markdown报告导出成功');
    } catch (error) {
      message.error('导出报告失败');
    }
  };

  const generateMarkdownReport = (report: Report): string => {
    const content = report.content || {};
    let markdown = `# ${report.title}\n\n`;
    
    markdown += `**报告类型**: ${report.report_type === 'evaluation' ? '评测报告' : report.report_type === 'performance' ? '性能报告' : '对比报告'}\n`;
    markdown += `**创建时间**: ${new Date(report.created_at).toLocaleString()}\n`;
    markdown += `**更新时间**: ${new Date(report.updated_at).toLocaleString()}\n\n`;
    
    if (report.description) {
      markdown += `## 描述\n\n${report.description}\n\n`;
    }
    
    if (report.report_type === 'evaluation') {
      markdown += generateEvaluationMarkdown(content);
    } else if (report.report_type === 'performance') {
      markdown += generatePerformanceMarkdown(content);
    } else if (report.report_type === 'comparison') {
      markdown += generateComparisonMarkdown(content);
    }
    
    // 添加数据可视化部分
    markdown += generateVisualizationMarkdown(content, report.report_type);
    
    return markdown;
  };

  const generateEvaluationMarkdown = (content: any): string => {
    let markdown = `## 评测摘要\n\n`;
    
    if (content.summary) {
      const summary = content.summary;
      markdown += `| 指标 | 值 |\n`;
      markdown += `|------|----|\n`;
      markdown += `| 测试名称 | ${summary.test_name || '-'} |\n`;
      markdown += `| 数据集名称 | ${summary.dataset_name || '-'} |\n`;
      markdown += `| 项目名称 | ${summary.project_name || '-'} |\n`;
      markdown += `| 总问题数 | ${summary.total_questions || 0} |\n`;
      markdown += `| 完成问题数 | ${summary.completed_questions || 0} |\n`;
      markdown += `| 完成率 | ${((summary.completion_rate || 0) * 100).toFixed(1)}% |\n`;
      markdown += `| 平均分数 | ${summary.average_score || 0} |\n`;
      markdown += `| 总体评分 | ${summary.overall_score || 0} |\n`;
      markdown += `| 评分方法 | ${summary.scoring_method || '-'} |\n`;
      markdown += `| 评测类型 | ${summary.evaluation_type || '-'} |\n\n`;
    }
    
    if (content.dimensions) {
      markdown += `## 维度评分\n\n`;
      markdown += `| 维度 | 平均分 | 最高分 | 最低分 | 题目数 |\n`;
      markdown += `|------|--------|--------|--------|--------|\n`;
      
      Object.entries(content.dimensions).forEach(([dimension, stats]: [string, any]) => {
        markdown += `| ${dimension} | ${stats.average || 0} | ${stats.max || 0} | ${stats.min || 0} | ${stats.count || 0} |\n`;
      });
      markdown += `\n`;
    }
    
    if (content.score_distribution) {
      markdown += `## 分数分布\n\n`;
      markdown += `| 分数 | 题目数 |\n`;
      markdown += `|------|--------|\n`;
      
      Object.entries(content.score_distribution).forEach(([score, count]: [string, any]) => {
        markdown += `| ${score}分 | ${count} |\n`;
      });
      markdown += `\n`;
    }
    
    if (content.detailed_results && content.detailed_results.length > 0) {
      markdown += `## 详细评测结果\n\n`;
      content.detailed_results.slice(0, 10).forEach((result: any, index: number) => {
        markdown += `### 问题 ${index + 1}\n\n`;
        markdown += `**问题**: ${result.question_text}\n\n`;
        markdown += `**RAG回答**: ${result.rag_answer}\n\n`;
        markdown += `**评分**: ${result.final_score}\n\n`;
        markdown += `**评测理由**: ${result.evaluation_reason}\n\n`;
        markdown += `---\n\n`;
      });
      
      if (content.detailed_results.length > 10) {
        markdown += `*注: 仅显示前10个详细结果，共${content.detailed_results.length}个问题*\n\n`;
      }
    }
    
    return markdown;
  };

  const generatePerformanceMarkdown = (content: any): string => {
    let markdown = `## 性能摘要\n\n`;
    
    if (content.summary) {
      const summary = content.summary;
      markdown += `| 指标 | 值 |\n`;
      markdown += `|------|----|\n`;
      markdown += `| 测试名称 | ${summary.test_name || '-'} |\n`;
      markdown += `| 项目名称 | ${summary.project_name || '-'} |\n`;
      markdown += `| 并发数 | ${summary.concurrency || 0} |\n`;
      markdown += `| 总请求数 | ${summary.total_requests || 0} |\n`;
      markdown += `| 成功请求数 | ${summary.successful_requests || 0} |\n`;
      markdown += `| 失败请求数 | ${summary.failed_requests || 0} |\n`;
      markdown += `| 成功率 | ${summary.success_rate || 0}% |\n`;
      markdown += `| 平均响应时间 | ${summary.average_response_time || 0}s |\n`;
      markdown += `| 平均首次响应时间 | ${summary.average_first_response_time || 0}s |\n`;
      markdown += `| 平均生成速度 | ${summary.average_generation_speed || 0}字符/秒 |\n\n`;
    }
    
    if (content.time_distribution) {
      markdown += `## 响应时间分布\n\n`;
      markdown += `| 时间范围 | 请求数 |\n`;
      markdown += `|----------|--------|\n`;
      
      Object.entries(content.time_distribution).forEach(([timeRange, count]: [string, any]) => {
        markdown += `| ${timeRange} | ${count} |\n`;
      });
      markdown += `\n`;
    }
    
    return markdown;
  };

  const generateComparisonMarkdown = (content: any): string => {
    let markdown = `## 对比摘要\n\n`;
    
    if (content.summary) {
      const summary = content.summary;
      markdown += `| 指标 | 值 |\n`;
      markdown += `|------|----|\n`;
      markdown += `| 项目名称 | ${summary.project_name || '-'} |\n`;
      markdown += `| 总测试数 | ${summary.total_tests || 0} |\n`;
      markdown += `| 精度测试数 | ${summary.accuracy_tests || 0} |\n`;
      markdown += `| 性能测试数 | ${summary.performance_tests || 0} |\n\n`;
    }
    
    if (content.comparison_data) {
      markdown += `## 测试对比\n\n`;
      content.comparison_data.forEach((test: any, index: number) => {
        markdown += `### ${test.test_name}\n\n`;
        markdown += `**类型**: ${test.test_type === 'accuracy' ? '精度测试' : '性能测试'}\n\n`;
        
        if (test.test_type === 'accuracy') {
          markdown += `- 总问题数: ${test.total_questions}\n`;
          markdown += `- 完成问题数: ${test.completed_questions}\n`;
          markdown += `- 平均分数: ${test.average_score}\n`;
          markdown += `- 总体评分: ${test.overall_score}\n\n`;
        } else {
          markdown += `- 并发数: ${test.concurrency}\n`;
          markdown += `- 总请求数: ${test.total_requests}\n`;
          markdown += `- 成功率: ${(test.success_rate * 100).toFixed(1)}%\n`;
          markdown += `- 平均响应时间: ${test.average_response_time}s\n\n`;
        }
      });
    }
    
    return markdown;
  };

  const generateVisualizationMarkdown = (content: any, reportType: string): string => {
    let markdown = `## 数据可视化\n\n`;
    
    if (reportType === 'evaluation') {
      markdown += generateEvaluationVisualization(content);
    } else if (reportType === 'performance') {
      markdown += generatePerformanceVisualization(content);
    } else if (reportType === 'comparison') {
      markdown += generateComparisonVisualization(content);
    }
    
    return markdown;
  };

  const generateEvaluationVisualization = (content: any): string => {
    let markdown = `### 分数分布图表\n\n`;
    
    if (content.score_distribution) {
      markdown += `**分数分布统计**:\n\n`;
      Object.entries(content.score_distribution).forEach(([score, count]: [string, any]) => {
        const percentage = content.summary?.total_questions ? 
          ((count as number) / content.summary.total_questions * 100).toFixed(1) : '0.0';
        markdown += `- ${score}分: ${count}题 (${percentage}%)\n`;
      });
      markdown += `\n`;
      
      // 生成简单的ASCII图表
      const maxCount = Math.max(...Object.values(content.score_distribution) as number[]);
      if (maxCount > 0) {
        markdown += `**分数分布条形图**:\n\n`;
        markdown += `\`\`\`\n`;
        Object.entries(content.score_distribution).forEach(([score, count]: [string, any]) => {
          const barLength = Math.round((count as number) / maxCount * 20);
          const bar = '█'.repeat(barLength);
          markdown += `${score}分 │${bar} ${count}\n`;
        });
        markdown += `\`\`\`\n\n`;
      }
    }
    
    if (content.dimensions) {
      markdown += `### 维度评分图表\n\n`;
      markdown += `**各维度平均分对比**:\n\n`;
      
      const maxScore = Math.max(...Object.values(content.dimensions).map((d: any) => d.average) as number[]);
      if (maxScore > 0) {
        markdown += `\`\`\`\n`;
        Object.entries(content.dimensions).forEach(([dimension, stats]: [string, any]) => {
          const barLength = Math.round(stats.average / maxScore * 20);
          const bar = '█'.repeat(barLength);
          markdown += `${dimension} │${bar} ${stats.average.toFixed(2)}\n`;
        });
        markdown += `\`\`\`\n\n`;
      }
    }
    
    if (content.summary) {
      markdown += `### 完成率趋势\n\n`;
      markdown += `**评测进度**:\n\n`;
      const completionRate = content.summary.completion_rate || 0;
      const progressBar = '█'.repeat(Math.round(completionRate * 20));
      const emptyBar = '░'.repeat(20 - Math.round(completionRate * 20));
      markdown += `\`\`\`\n`;
      markdown += `进度: [${progressBar}${emptyBar}] ${(completionRate * 100).toFixed(1)}%\n`;
      markdown += `\`\`\`\n\n`;
    }
    
    return markdown;
  };

  const generatePerformanceVisualization = (content: any): string => {
    let markdown = `### 响应时间分布图表\n\n`;
    
    if (content.time_distribution) {
      markdown += `**响应时间分布统计**:\n\n`;
      Object.entries(content.time_distribution).forEach(([timeRange, count]: [string, any]) => {
        const percentage = content.summary?.total_requests ? 
          ((count as number) / content.summary.total_requests * 100).toFixed(1) : '0.0';
        markdown += `- ${timeRange}: ${count}次 (${percentage}%)\n`;
      });
      markdown += `\n`;
      
      // 生成简单的ASCII图表
      const maxCount = Math.max(...Object.values(content.time_distribution) as number[]);
      if (maxCount > 0) {
        markdown += `**响应时间分布条形图**:\n\n`;
        markdown += `\`\`\`\n`;
        Object.entries(content.time_distribution).forEach(([timeRange, count]: [string, any]) => {
          const barLength = Math.round((count as number) / maxCount * 20);
          const bar = '█'.repeat(barLength);
          markdown += `${timeRange} │${bar} ${count}\n`;
        });
        markdown += `\`\`\`\n\n`;
      }
    }
    
    if (content.summary) {
      markdown += `### 成功率饼图\n\n`;
      markdown += `**请求成功/失败分布**:\n\n`;
      const successCount = content.summary.successful_requests || 0;
      const failCount = content.summary.failed_requests || 0;
      const total = successCount + failCount;
      
      if (total > 0) {
        const successRate = (successCount / total * 100).toFixed(1);
        const failRate = (failCount / total * 100).toFixed(1);
        
        markdown += `- 成功: ${successCount}次 (${successRate}%)\n`;
        markdown += `- 失败: ${failCount}次 (${failRate}%)\n\n`;
        
        // 生成简单的ASCII饼图
        const successBar = '█'.repeat(Math.round(successCount / total * 20));
        const failBar = '░'.repeat(20 - Math.round(successCount / total * 20));
        markdown += `\`\`\`\n`;
        markdown += `成功率: [${successBar}${failBar}] ${successRate}%\n`;
        markdown += `\`\`\`\n\n`;
      }
    }
    
    return markdown;
  };

  const generateComparisonVisualization = (content: any): string => {
    let markdown = `### 测试对比图表\n\n`;
    
    if (content.comparison_data) {
      markdown += `**测试对比统计**:\n\n`;
      
      // 精度测试对比
      const accuracyTests = content.comparison_data.filter((test: any) => test.test_type === 'accuracy');
      if (accuracyTests.length > 0) {
        markdown += `#### 精度测试对比\n\n`;
        const maxScore = Math.max(...accuracyTests.map((test: any) => test.average_score || 0));
        if (maxScore > 0) {
          markdown += `\`\`\`\n`;
          accuracyTests.forEach((test: any) => {
            const barLength = Math.round((test.average_score || 0) / maxScore * 20);
            const bar = '█'.repeat(barLength);
            markdown += `${test.test_name} │${bar} ${test.average_score || 0}\n`;
          });
          markdown += `\`\`\`\n\n`;
        }
      }
      
      // 性能测试对比
      const performanceTests = content.comparison_data.filter((test: any) => test.test_type === 'performance');
      if (performanceTests.length > 0) {
        markdown += `#### 性能测试对比\n\n`;
        const maxRequests = Math.max(...performanceTests.map((test: any) => test.total_requests || 0));
        if (maxRequests > 0) {
          markdown += `\`\`\`\n`;
          performanceTests.forEach((test: any) => {
            const barLength = Math.round((test.total_requests || 0) / maxRequests * 20);
            const bar = '█'.repeat(barLength);
            markdown += `${test.test_name} │${bar} ${test.total_requests || 0}\n`;
          });
          markdown += `\`\`\`\n\n`;
        }
      }
    }
    
    return markdown;
  };

  const renderReportContent = (report: Report) => {
    if (!report.content) return null;

    const content = report.content;

    if (report.report_type === 'evaluation') {
      return (
        <div>
          {/* 评测报告内容 */}
          {content.summary && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>评测摘要</Title>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}>
                  <Statistic title="测试名称" value={content.summary.test_name} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="总问题数" value={content.summary.total_questions} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="完成问题数" value={content.summary.completed_questions} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="完成率" value={`${(content.summary.completion_rate * 100).toFixed(1)}%`} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="平均分数" value={content.summary.average_score} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="总体评分" value={content.summary.overall_score} />
                </Col>
              </Row>
            </div>
          )}

          {content.dimensions && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>维度评分</Title>
              <Row gutter={[16, 16]}>
                {Object.entries(content.dimensions).map(([dimension, stats]: [string, any]) => (
                  <Col xs={24} md={8} key={dimension}>
                    <Card>
                      <Statistic
                        title={dimension}
                        value={stats.average}
                        precision={2}
                        suffix={`(${stats.count}题)`}
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {content.score_distribution && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>分数分布</Title>
              <Row gutter={[16, 16]}>
                {Object.entries(content.score_distribution).map(([score, count]: [string, any]) => (
                  <Col xs={24} md={4} key={score}>
                    <Card>
                      <Statistic title={`${score}分`} value={count} />
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}

          {content.detailed_results && content.detailed_results.length > 0 && (
            <div>
              <Title level={5}>详细评测结果</Title>
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {content.detailed_results.map((result: any, index: number) => (
                  <Card key={index} style={{ marginBottom: '8px' }}>
                    <div>
                      <Text strong>问题: </Text>
                      <Text>{result.question_text}</Text>
                    </div>
                    <div style={{ marginTop: '8px' }}>
                      <Text strong>RAG回答: </Text>
                      <Text>{result.rag_answer}</Text>
                    </div>
                    <div style={{ marginTop: '8px' }}>
                      <Text strong>评分: </Text>
                      <Tag color="blue">{result.final_score}</Tag>
                      <Text strong style={{ marginLeft: '16px' }}>评测理由: </Text>
                      <Text>{result.evaluation_reason}</Text>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    if (report.report_type === 'performance') {
      return (
        <div>
          {/* 性能测试报告内容 */}
          {content.summary && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>性能摘要</Title>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}>
                  <Statistic title="测试名称" value={content.summary.test_name} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="并发数" value={content.summary.concurrency} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="总请求数" value={content.summary.total_requests} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="成功请求数" value={content.summary.successful_requests} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="成功率" value={`${content.summary.success_rate}%`} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="平均响应时间" value={`${content.summary.average_response_time}s`} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="平均首次响应时间" value={`${content.summary.average_first_response_time}s`} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="平均生成速度" value={`${content.summary.average_generation_speed}字符/秒`} />
                </Col>
              </Row>
            </div>
          )}

          {content.time_distribution && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>响应时间分布</Title>
              <Row gutter={[16, 16]}>
                {Object.entries(content.time_distribution).map(([timeRange, count]: [string, any]) => (
                  <Col xs={24} md={4} key={timeRange}>
                    <Card>
                      <Statistic title={timeRange} value={count} />
                    </Card>
                  </Col>
                ))}
              </Row>
            </div>
          )}
        </div>
      );
    }

    if (report.report_type === 'comparison') {
      return (
        <div>
          {/* 对比报告内容 */}
          {content.summary && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>对比摘要</Title>
              <Row gutter={[16, 16]}>
                <Col xs={24} md={8}>
                  <Statistic title="项目名称" value={content.summary.project_name} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="总测试数" value={content.summary.total_tests} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="精度测试数" value={content.summary.accuracy_tests} />
                </Col>
                <Col xs={24} md={8}>
                  <Statistic title="性能测试数" value={content.summary.performance_tests} />
                </Col>
              </Row>
            </div>
          )}

          {content.comparison_data && (
            <div style={{ marginBottom: '24px' }}>
              <Title level={5}>测试对比</Title>
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {content.comparison_data.map((test: any, index: number) => (
                  <Card key={index} style={{ marginBottom: '8px' }}>
                    <div>
                      <Text strong>{test.test_name}</Text>
                      <Tag color={test.test_type === 'accuracy' ? 'blue' : 'green'} style={{ marginLeft: '8px' }}>
                        {test.test_type === 'accuracy' ? '精度测试' : '性能测试'}
                      </Tag>
                    </div>
                    {test.test_type === 'accuracy' && (
                      <div style={{ marginTop: '8px' }}>
                        <Text>总问题数: {test.total_questions} | </Text>
                        <Text>完成问题数: {test.completed_questions} | </Text>
                        <Text>平均分数: {test.average_score} | </Text>
                        <Text>总体评分: {test.overall_score}</Text>
                      </div>
                    )}
                    {test.test_type === 'performance' && (
                      <div style={{ marginTop: '8px' }}>
                        <Text>并发数: {test.concurrency} | </Text>
                        <Text>总请求数: {test.total_requests} | </Text>
                        <Text>成功率: {(test.success_rate * 100).toFixed(1)}% | </Text>
                        <Text>平均响应时间: {test.average_response_time}s</Text>
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      );
    }

    // 默认显示原始JSON
    return <pre>{JSON.stringify(content, null, 2)}</pre>;
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!report) {
    return (
      <Layout.Content style={{ padding: '24px' }}>
        <Empty description="报告不存在" />
      </Layout.Content>
    );
  }

  return (
    <Layout.Content style={{ padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate(`/projects/${projectId}?tab=reports`)}
        >
          返回项目详情
        </Button>
        <Title level={3}>{report.title}</Title>
        <Space>
          <Button 
            icon={<ReloadOutlined />}
            onClick={handleRefreshReport}
            loading={loading}
          >
            刷新数据
          </Button>
          <Button 
            icon={<DownloadOutlined />}
            onClick={handleExportReport}
          >
            导出MD
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="报告类型"
              value={report.report_type}
              prefix={<BarChartOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="公开状态"
              value={report.public ? '公开' : '私有'}
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card>
            <Statistic
              title="创建时间"
              value={new Date(report.created_at).toLocaleDateString()}
            />
          </Card>
        </Col>
      </Row>

      {report.description && (
        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>描述</Title>
          <Paragraph>{report.description}</Paragraph>
        </Card>
      )}

      {report.content && (
        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>报告内容</Title>
          <div style={{ minHeight: '400px' }}>
            {renderReportContent(report)}
          </div>
        </Card>
      )}

      {/* 数据可视化图表 */}
      {report.content && (
        <Card style={{ marginTop: '16px' }}>
          <Title level={5}>数据可视化</Title>
          <ReportCharts reportType={report.report_type} content={report.content} />
        </Card>
      )}
    </Layout.Content>
  );
};

export default ReportDetailPage;
