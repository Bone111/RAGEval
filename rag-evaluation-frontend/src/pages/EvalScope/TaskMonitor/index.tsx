/**
 * EvalScope任务监控页面
 */
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Progress,
  Statistic,
  Row,
  Col,
  Timeline,
  Tag,
  Space,
  Button,
  Divider,
  Alert,
  Spin,
  Collapse
} from 'antd';
import {
  ClockCircleOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  ArrowLeftOutlined,
  ReloadOutlined,
  BarChartOutlined
} from '@ant-design/icons';
import { formatRunningTime } from '../../../utils/timeFormat';
import type { EvalTaskDetail, WebSocketMessage } from '@/types/evalscope.types';
import { evalscopeService } from '@/services/evalscope.service';
import { useEvalTaskWebSocket } from '@/hooks/useEvalTaskWebSocket';
import { useSharedTaskPolling } from '@/hooks/useSharedTaskPolling';
import DetailedProgressComponent from '../../../components/DetailedProgress';

const TaskMonitorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const taskId = Number(id);
  const navigate = useNavigate();
  
  const [task, setTask] = useState<EvalTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [logs, setLogs] = useState<string[]>([]);
  const [datasetProgress, setDatasetProgress] = useState<any>(null);
  
  // 使用共享轮询机制
  const { refreshTask } = useSharedTaskPolling(taskId, {
    enabled: true,
    onTaskUpdate: (updatedTask) => {
      setTask(updatedTask as EvalTaskDetail);
    }
  });

  // 初始加载任务
  useEffect(() => {
    loadTask();
  }, [taskId]);

  // 根据任务状态生成日志
  useEffect(() => {
    if (!task) return;
    
    const baseLogs = [
      `[${new Date(task.created_at).toLocaleTimeString()}] 📝 任务创建: ${task.task_name}`,
      `[${new Date(task.created_at).toLocaleTimeString()}] 🤖 模型: ${task.model_id}`,
      `[${new Date(task.created_at).toLocaleTimeString()}] 📊 数据集: ${task.datasets.join(', ')} (共${task.datasets.length}个)`,
    ];
    
    if (task.started_at) {
      baseLogs.push(`[${new Date(task.started_at).toLocaleTimeString()}] 🚀 任务开始执行`);
      
      // 添加详细的执行阶段日志
      if (task.status === 'running') {
        const progressStages = [
          { threshold: 5, message: '⚙️ 初始化评测环境' },
          { threshold: 15, message: '📥 加载模型和数据集' },
          { threshold: 30, message: '🔄 开始批量推理...' },
          { threshold: 60, message: '📈 评测进行中，正在处理样本...' },
          { threshold: 90, message: '📋 生成评测报告...' },
        ];
        
        for (const stage of progressStages) {
          if (task.progress >= stage.threshold) {
            const estimatedTime = new Date(new Date(task.started_at).getTime() + (stage.threshold / 100 * 2 * 60000));
            baseLogs.push(`[${estimatedTime.toLocaleTimeString()}] ${stage.message}`);
          }
        }
        
        // 当前状态
        baseLogs.push(`[${new Date().toLocaleTimeString()}] ⏳ 进度: ${task.progress}% - 评测正在进行中`);
      }
    }
    
    if (task.status === 'completed') {
      if (task.completed_at) {
        baseLogs.push(`[${new Date(task.completed_at).toLocaleTimeString()}] ✅ 任务执行完成`);
      }
      if (task.results && task.results.length > 0) {
        baseLogs.push(`[${new Date().toLocaleTimeString()}] 📈 找到 ${task.results.length} 个评测结果，生成报告完成`);
        
        // 添加最佳结果信息
        const bestResult = task.results.reduce((best, current) => 
          (current.metric_value || 0) > (best.metric_value || 0) ? current : best
        );
        if (bestResult.metric_value && bestResult.metric_value > 0) {
          baseLogs.push(`[${new Date().toLocaleTimeString()}] 🏆 最佳表现: ${bestResult.benchmark} - ${(bestResult.metric_value * 100).toFixed(1)}%`);
        }
      }
    } else if (task.status === 'failed' && task.error_message) {
      baseLogs.push(`[${new Date().toLocaleTimeString()}] ❌ 任务失败: ${task.error_message}`);
      baseLogs.push(`[${new Date().toLocaleTimeString()}] 💡 提示: 检查模型配置和系统资源`);
    }
    
    setLogs(baseLogs);
  }, [task]);

  const loadTask = async () => {
    try {
      const data = await evalscopeService.getTask(taskId);
      setTask(data);
      
      // 获取数据集进度详情
      try {
        const progressData = await evalscopeService.getTaskDatasetProgress(taskId);
        setDatasetProgress(progressData);
      } catch (progressErr) {
        console.warn('获取数据集进度失败:', progressErr);
        // 不影响主要功能，只记录警告
      }
      
      setLoading(false);
    } catch (error) {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    try {
      await evalscopeService.cancelTask(taskId);
      // 使用共享轮询的刷新方法
      await refreshTask();
    } catch (error) {
      //
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px' }}>
        <Spin size="large" tip="加载任务信息..." />
      </div>
    );
  }

  if (!task) {
    return (
      <div style={{ padding: '24px' }}>
        <Alert
          message="任务不存在"
          description="无法找到该评测任务，可能已被删除"
          type="error"
          showIcon
        />
      </div>
    );
  }

  // 状态渲染
  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; icon: any }> = {
      pending: { color: 'default', icon: <ClockCircleOutlined /> },
      running: { color: 'processing', icon: <RocketOutlined /> },
      completed: { color: 'success', icon: <CheckCircleOutlined /> },
      failed: { color: 'error', icon: <CloseCircleOutlined /> },
      cancelled: { color: 'warning', icon: <PauseCircleOutlined /> }
    };

    const config = statusMap[status] || statusMap.pending;
    return <Tag icon={config.icon} color={config.color}>{status.toUpperCase()}</Tag>;
  };

  return (
    <div style={{ padding: '24px' }}>
      {/* 头部 */}
      <div style={{ marginBottom: 24 }}>
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/evalscope/tasks')}
          >
            返回列表
          </Button>
          <Button icon={<ReloadOutlined />} onClick={refreshTask}>
            刷新
          </Button>
          {task.status === 'running' && (
            <Button danger onClick={handleCancel}>
              取消任务
            </Button>
          )}
          <Tag color="blue">真实评测模式</Tag>
        </Space>
      </div>

      {/* 性能提醒 */}
      {task.status === 'running' && (
        <Alert
          message="⚡ 评测任务正在运行中"
          description={
            <div>
              <p>🔥 <strong>性能提醒：</strong>评测任务会占用大量CPU和内存资源，可能导致电脑运行缓慢。</p>
              <p>💡 <strong>建议：</strong>关闭不必要的程序，避免同时运行其他高性能任务。</p>
              <p>⏱️ <strong>预计时间：</strong>{task.datasets.length} 个数据集 × 2-5分钟/数据集</p>
              <p>📊 页面会每2秒自动刷新任务状态，无需手动刷新。</p>
            </div>
          }
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 任务完成提示 */}
      {task.status === 'completed' && (
        <Alert
          message="🎉 评测任务已完成！"
          description={
            <div>
              <p>✅ 任务已成功完成，您可以查看详细结果。</p>
              <p>📈 点击下方的"查看详细结果"按钮查看完整的评测报告和图表分析。</p>
            </div>
          }
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
          action={
            <Button
              type="primary"
              onClick={() => navigate(`/evalscope/tasks/${task.id}/results`)}
              icon={<BarChartOutlined />}
            >
              查看详细结果
            </Button>
          }
        />
      )}

      {/* 任务失败提示 */}
      {task.status === 'failed' && (
        <Alert
          message="❌ 评测任务失败"
          description={
            <div>
              <p>任务执行过程中遇到错误，请检查错误信息并重新尝试。</p>
              <p>💡 常见解决方案：检查模型配置、网络连接或系统资源是否充足。</p>
            </div>
          }
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 任务基本信息 */}
      <Card title={`任务监控 - ${task.task_name}`} extra={getStatusTag(task.status)}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="模型" value={task.model_id} />
          </Col>
          <Col span={6}>
            <Statistic title="数据集" value={task.datasets.length} suffix="个" />
          </Col>
          <Col span={6}>
            <Statistic title="评测后端" value={task.eval_backend} />
          </Col>
          <Col span={6}>
            <Statistic
              title="创建时间"
              value={new Date(task.created_at).toLocaleString()}
            />
          </Col>
        </Row>
      </Card>

      {/* 进度条 - 检查是否有详细进度信息 */}
      <Card title="任务进度" style={{ marginTop: 16 }}>
        {task.extra_metadata?.detailed_progress_metadata ? (
          // 显示详细进度信息
          <DetailedProgressComponent
            progress={task.progress}
            detailedProgress={task.extra_metadata.detailed_progress_metadata}
          />
        ) : (
          // 显示简单进度条
          <Progress
            percent={task.progress}
            status={task.status === 'running' ? 'active' : task.status === 'completed' ? 'success' : undefined}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />
        )}
        <div style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Statistic
                title="开始时间"
                value={task.started_at ? new Date(task.started_at).toLocaleString() : '未开始'}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="完成时间"
                value={task.completed_at ? new Date(task.completed_at).toLocaleString() : '进行中'}
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="耗时"
                value={
                  task.started_at
                    ? formatRunningTime(task.started_at, task.completed_at)
                    : 'N/A'
                }
              />
            </Col>
          </Row>
        </div>
      </Card>

      {/* 数据集进度 */}
      <Card title="数据集进度" style={{ marginTop: 16 }}>
        {task.datasets.map((dataset, index) => {
          // 计算每个数据集的结果指标
          const datasetResults = task.results?.filter(r => r.benchmark === dataset) || [];
          const metricsCount = datasetResults.length;
          
          // 获取详细的数据集进度信息
          const getDatasetProgressInfo = () => {
            if (datasetProgress?.dataset_progress?.[dataset]) {
              const progressInfo = datasetProgress.dataset_progress[dataset];
              return {
                progress: progressInfo.overall_progress,
                status: progressInfo.status,
                subsets: progressInfo.subsets,
                totalCompleted: progressInfo.total_completed,
                totalExpected: progressInfo.total_expected
              };
            }
            
            // 回退到原有逻辑
            if (task.status === 'completed') {
              return { progress: 100, status: 'completed', subsets: null };
            } else if (task.status === 'running') {
              if (metricsCount > 0) {
                return { progress: 100, status: 'completed', subsets: null };
              } else {
                return { progress: Math.min(task.progress, 90), status: 'running', subsets: null };
              }
            } else {
              return { progress: 0, status: 'pending', subsets: null };
            }
          };

          const progressInfo = getDatasetProgressInfo();
          const isCompleted = progressInfo.status === 'completed';
          const isRunning = progressInfo.status === 'running';

          // 获取该数据集的详细指标信息
          const getMetricsDisplay = () => {
            if (metricsCount === 0) {
              return <Tag color="default">0 个指标</Tag>;
            }
            
            // 显示指标统计
            const metricNames = [...new Set(datasetResults.map(r => r.metric_name))];
            return (
              <Space size={4}>
                <Tag color="blue">{metricsCount} 个指标</Tag>
                {metricNames.slice(0, 2).map(name => (
                  <Tag key={name} color="cyan" style={{ fontSize: '11px' }}>
                    {name}
                  </Tag>
                ))}
                {metricNames.length > 2 && (
                  <Tag color="cyan" style={{ fontSize: '11px' }}>
                    +{metricNames.length - 2}
                  </Tag>
                )}
              </Space>
            );
          };

          return (
            <div key={dataset} style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontWeight: 'bold' }}>{dataset}</span>
                <Space>
                  <Tag color={isCompleted ? 'success' : isRunning ? 'processing' : 'default'}>
                    {isCompleted ? '已完成' : isRunning ? '进行中' : '等待中'}
                  </Tag>
                  {getMetricsDisplay()}
                </Space>
              </div>
              <Progress
                percent={progressInfo.progress}
                size="small"
                status={isCompleted ? 'success' : isRunning ? 'active' : undefined}
                strokeColor={isCompleted ? '#52c41a' : isRunning ? '#1890ff' : '#d9d9d9'}
              />
              
              {/* 显示样本进度信息 */}
              {progressInfo.totalCompleted !== undefined && progressInfo.totalExpected !== undefined && (
                <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                  样本进度: {progressInfo.totalCompleted}/{progressInfo.totalExpected}
                </div>
              )}
              
              {/* 显示子集进度详情 */}
              {progressInfo.subsets && Object.keys(progressInfo.subsets).length > 1 && (
                <Collapse size="small" style={{ marginTop: '8px' }}>
                  <Collapse.Panel header="子集进度详情" key="subsets">
                    {Object.entries(progressInfo.subsets).map(([subsetName, subsetInfo]: [string, any]) => (
                      <div key={subsetName} style={{ marginBottom: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 'bold' }}>{subsetName}</span>
                          <span style={{ fontSize: '12px', color: '#666' }}>
                            {subsetInfo.completed_samples}/{subsetInfo.total_samples}
                          </span>
                        </div>
                        <Progress
                          percent={subsetInfo.progress}
                          size="small"
                          showInfo={false}
                          strokeColor={subsetInfo.progress === 100 ? '#52c41a' : '#1890ff'}
                        />
                      </div>
                    ))}
                  </Collapse.Panel>
                </Collapse>
              )}
              
              {/* 显示指标详情 */}
              {isCompleted && metricsCount > 0 && (
                <div style={{ 
                  marginTop: 6, 
                  padding: '6px 10px', 
                  background: '#f6ffed', 
                  borderRadius: '4px',
                  fontSize: '12px',
                  color: '#52c41a'
                }}>
                  ✓ 完成 {metricsCount} 项指标评测
                  {datasetResults.some(r => r.metric_value) && (
                    <span style={{ marginLeft: 8, color: '#389e0d' }}>
                      · 平均得分: {(datasetResults.reduce((sum, r) => sum + (r.metric_value || 0), 0) / metricsCount * 100).toFixed(1)}%
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}
        
        {/* 整体统计 */}
        {task.results && task.results.length > 0 && (
          <div style={{ 
            marginTop: 16, 
            padding: '10px 12px', 
            background: '#e6f7ff', 
            borderRadius: '6px',
            border: '1px solid #91d5ff'
          }}>
            <Row gutter={16}>
              <Col span={8}>
                <div style={{ fontSize: '12px', color: '#666' }}>总指标数</div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#1890ff' }}>
                  {task.results.length}
                </div>
              </Col>
              <Col span={8}>
                <div style={{ fontSize: '12px', color: '#666' }}>已完成数据集</div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#52c41a' }}>
                  {task.datasets.filter(d => 
                    task.results?.some(r => r.benchmark === d)
                  ).length} / {task.datasets.length}
                </div>
              </Col>
              <Col span={8}>
                <div style={{ fontSize: '12px', color: '#666' }}>指标类型</div>
                <div style={{ fontSize: '18px', fontWeight: 'bold', color: '#722ed1' }}>
                  {[...new Set(task.results.map(r => r.metric_name))].length}
                </div>
              </Col>
            </Row>
          </div>
        )}
        
        {/* 并行处理说明 */}
        {task.status === 'running' && task.datasets.length > 1 && (
          <div style={{ marginTop: 12, padding: '8px 12px', background: '#f0f9ff', borderRadius: '6px', border: '1px solid #bae7ff' }}>
            <div style={{ fontSize: '12px', color: '#1890ff' }}>
              🚀 <strong>并行处理模式：</strong>所有数据集同时进行评测，提升执行效率
            </div>
          </div>
        )}
      </Card>

      {/* 实时日志 */}
      <Card title="运行日志" style={{ marginTop: 16 }}>
        <Timeline mode="left">
          {logs.length === 0 && (
            <Timeline.Item color="gray">暂无日志</Timeline.Item>
          )}
          {logs.slice(-20).map((log, index) => (
            <Timeline.Item key={index} color={
              log.includes('[error]') ? 'red' :
              log.includes('[warning]') ? 'orange' :
              'blue'
            }>
              {log}
            </Timeline.Item>
          ))}
        </Timeline>
      </Card>

      {/* 错误信息 */}
      {task.error_message && (
        <Card title="错误信息" style={{ marginTop: 16 }}>
          <Alert
            message="任务执行失败"
            description={task.error_message}
            type="error"
            showIcon
          />
        </Card>
      )}

      {/* 即时结果 */}
      {task.results && task.results.length > 0 && (
        <Card title="评测结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            {task.results.map((result) => (
              <Col span={8} key={result.id} style={{ marginBottom: 16 }}>
                <Statistic
                  title={`${result.benchmark} - ${result.metric_name}`}
                  value={result.metric_value}
                  suffix="%"
                  precision={1}
                />
              </Col>
            ))}
          </Row>
          {task.status === 'completed' && (
          <div style={{ marginTop: 16 }}>
            <Space>
              <Button
                onClick={() => navigate(`/evalscope/tasks`)}
                icon={<ArrowLeftOutlined />}
              >
                返回任务列表
              </Button>
              <Button
                type="primary"
                onClick={() => navigate(`/evalscope/tasks/${task.id}/results`)}
                icon={<BarChartOutlined />}
              >
                查看详细结果
              </Button>
              <Button
                onClick={() => navigate(`/evalscope/tasks/create`)}
              >
                创建新任务
              </Button>
            </Space>
          </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default TaskMonitorPage;

