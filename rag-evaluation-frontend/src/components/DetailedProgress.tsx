import React from 'react';
import { Progress, Tag, Space, Card, List, Typography, Tooltip, Badge, Collapse } from 'antd';
import { CheckCircleOutlined, SyncOutlined, ClockCircleOutlined, ExclamationCircleOutlined, DownOutlined } from '@ant-design/icons';
import type { DetailedProgress, DatasetProgress, SubsetProgress } from '../types/evalscope.types';

const { Text } = Typography;
const { Panel } = Collapse;

interface DetailedProgressProps {
  progress: number;
  detailedProgress?: DetailedProgress;
  style?: React.CSSProperties;
}

const DetailedProgressComponent: React.FC<DetailedProgressProps> = ({ 
  progress, 
  detailedProgress, 
  style 
}) => {
  if (!detailedProgress || !detailedProgress.dataset_progress || detailedProgress.dataset_progress.length === 0) {
    // 回退到简单进度条
    return <Progress percent={progress} size="small" />;
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'running':
        return <SyncOutlined spin style={{ color: '#1890ff' }} />;
      case 'failed':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'waiting':
      default:
        return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'processing';
      case 'failed': return 'error';
      case 'waiting': 
      default: return 'default';
    }
  };

  const getPhaseText = (phase: string) => {
    const phaseMap = {
      'initializing': '初始化中',
      'loading_model': '加载模型',
      'evaluating': '评测中',
      'processing_results': '处理结果',
      'completed': '已完成'
    };
    return phaseMap[phase as keyof typeof phaseMap] || phase;
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return null;
    
    const startTime = new Date(start);
    const endTime = end ? new Date(end) : new Date();
    const duration = Math.floor((endTime.getTime() - startTime.getTime()) / 1000);
    
    if (duration < 60) return `${duration}秒`;
    if (duration < 3600) return `${Math.floor(duration / 60)}分${duration % 60}秒`;
    return `${Math.floor(duration / 3600)}时${Math.floor((duration % 3600) / 60)}分`;
  };

  return (
    <div style={style}>
      {/* 整体进度和阶段 */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <Space>
            <Text strong>整体进度</Text>
            <Tag color="blue">{getPhaseText(detailedProgress.phase)}</Tag>
          </Space>
          <Text type="secondary">
            {detailedProgress.completed_datasets} / {detailedProgress.total_datasets} 数据集
          </Text>
        </div>
        <Progress 
          percent={detailedProgress.overall_progress} 
          status={detailedProgress.phase === 'completed' ? 'success' : 'active'}
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
        {detailedProgress.message && (
          <Text type="secondary" style={{ fontSize: '12px', marginTop: 4, display: 'block' }}>
            {detailedProgress.message}
          </Text>
        )}
      </div>

      {/* 数据集进度列表 */}
      <Card 
        size="small" 
        title={
          <Space>
            <span>数据集进度</span>
            <Badge 
              count={detailedProgress.dataset_progress.filter(d => d.status === 'running').length} 
              showZero={false}
              style={{ backgroundColor: '#52c41a' }}
            />
          </Space>
        }
        style={{ backgroundColor: '#fafafa' }}
      >
        <List
          size="small"
          dataSource={detailedProgress.dataset_progress}
          renderItem={(dataset: DatasetProgress) => (
            <List.Item style={{ padding: '8px 0', borderBottom: '1px solid #f0f0f0' }}>
              <div style={{ width: '100%' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <Space>
                    {getStatusIcon(dataset.status)}
                    <Text strong>{dataset.name}</Text>
                    <Tag color={getStatusColor(dataset.status)} size="small">
                      {dataset.status === 'waiting' && '等待中'}
                      {dataset.status === 'running' && '运行中'}
                      {dataset.status === 'completed' && '已完成'}
                      {dataset.status === 'failed' && '失败'}
                    </Tag>
                  </Space>
                  <Space>
                    {dataset.status === 'running' && dataset.current_step && (
                      <Text type="secondary" style={{ fontSize: '12px' }}>
                        {dataset.current_step}
                      </Text>
                    )}
                    {(dataset.status === 'running' || dataset.status === 'completed') && (
                      <Tooltip title={formatDuration(dataset.start_time, dataset.end_time)}>
                        <Text type="secondary" style={{ fontSize: '12px' }}>
                          {formatDuration(dataset.start_time, dataset.end_time)}
                        </Text>
                      </Tooltip>
                    )}
                  </Space>
                </div>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Progress 
                    percent={dataset.progress} 
                    size="small" 
                    style={{ flex: 1 }}
                    status={dataset.status === 'failed' ? 'exception' : 
                           dataset.status === 'completed' ? 'success' : 'active'}
                  />
                  {dataset.total_samples && (
                    <Text type="secondary" style={{ fontSize: '12px', minWidth: 'auto', whiteSpace: 'nowrap' }}>
                      {dataset.completed_samples || 0} / {dataset.total_samples}
                    </Text>
                  )}
                </div>
              </div>
            </List.Item>
          )}
        />
      </Card>

      {/* 子集进度显示 */}
      {detailedProgress.subset_progress && detailedProgress.subset_progress.length > 0 && (
        <Card 
          size="small" 
          title={
            <Space>
              <span>子集进度</span>
              <Badge 
                count={detailedProgress.subset_progress.filter(s => s.status === 'running').length} 
                showZero={false}
                style={{ backgroundColor: '#1890ff' }}
              />
            </Space>
          }
          style={{ backgroundColor: '#fafafa', marginTop: 12 }}
        >
          <Collapse 
            size="small" 
            ghost
            expandIcon={({ isActive }) => <DownOutlined rotate={isActive ? 180 : 0} />}
          >
            <Panel 
              header={
                <Space>
                  <Text>当前子集: {detailedProgress.subset_progress.find(s => s.status === 'running')?.name || '无'}</Text>
                  <Text type="secondary">
                    ({detailedProgress.subset_progress.filter(s => s.status === 'completed').length} / {detailedProgress.subset_progress.length} 完成)
                  </Text>
                </Space>
              } 
              key="subsets"
            >
              <List
                size="small"
                dataSource={detailedProgress.subset_progress}
                renderItem={(subset: SubsetProgress) => (
                  <List.Item style={{ padding: '4px 0', borderBottom: '1px solid #f0f0f0' }}>
                    <div style={{ width: '100%' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                        <Space>
                          {getStatusIcon(subset.status)}
                          <Text strong style={{ fontSize: '12px' }}>{subset.name}</Text>
                          <Tag color={getStatusColor(subset.status)} size="small">
                            {subset.status === 'waiting' && '等待'}
                            {subset.status === 'running' && '运行'}
                            {subset.status === 'completed' && '完成'}
                            {subset.status === 'failed' && '失败'}
                          </Tag>
                        </Space>
                        <Space>
                          {subset.total > 0 && (
                            <Text type="secondary" style={{ fontSize: '11px' }}>
                              {subset.completed} / {subset.total}
                            </Text>
                          )}
                          {subset.last_updated && (
                            <Tooltip title={new Date(subset.last_updated).toLocaleString()}>
                              <Text type="secondary" style={{ fontSize: '11px' }}>
                                {new Date(subset.last_updated).toLocaleTimeString()}
                              </Text>
                            </Tooltip>
                          )}
                        </Space>
                      </div>
                      
                      <Progress 
                        percent={subset.progress} 
                        size="small" 
                        style={{ height: 4 }}
                        status={subset.status === 'failed' ? 'exception' : 
                               subset.status === 'completed' ? 'success' : 'active'}
                        showInfo={false}
                      />
                    </div>
                  </List.Item>
                )}
              />
            </Panel>
          </Collapse>
        </Card>
      )}
    </div>
  );
};

export default DetailedProgressComponent;

