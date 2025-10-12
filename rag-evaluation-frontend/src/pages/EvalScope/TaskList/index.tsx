/**
 * EvalScope任务列表页面
 */
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Select,
  Input,
  message,
  Alert,
  Modal,
  Checkbox,
  Tooltip
} from 'antd';
import {
  PlusOutlined,
  EyeOutlined,
  DeleteOutlined,
  ReloadOutlined,
  StopOutlined,
  SwapOutlined,
  RedoOutlined
} from '@ant-design/icons';
import type { EvalTask } from '../../../types/evalscope.types';
import { evalscopeService } from '../../../services/evalscope.service';
import SharedTaskPollingManager from '../../../hooks/useSharedTaskPolling';

const { Search } = Input;

const TaskListPage: React.FC = () => {
  const [tasks, setTasks] = useState<EvalTask[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [current, setCurrent] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedRows, setSelectedRows] = useState<number[]>([]);
  const [deletingTaskId, setDeletingTaskId] = useState<number | null>(null);
  const [modelValidations, setModelValidations] = useState<Record<number, any>>({});
  const navigate = useNavigate();

  useEffect(() => {
    loadTasks();
  }, [current, statusFilter]);

  // 使用共享轮询机制更新运行中的任务
  const runningTaskIds = tasks.filter(task => task.status === 'running').map(task => task.id);
  
  // 为每个运行中的任务订阅更新
  useEffect(() => {
    if (runningTaskIds.length === 0) return;

    const manager = SharedTaskPollingManager.getInstance();
    const unsubscribeFunctions: (() => void)[] = [];

    runningTaskIds.forEach(taskId => {
      const unsubscribe = manager.subscribe(taskId, (updatedTask) => {
        setTasks(prevTasks => 
          prevTasks.map(task => 
            task.id === taskId ? updatedTask as EvalTask : task
          )
        );
      });
      unsubscribeFunctions.push(unsubscribe);
    });

    return () => {
      unsubscribeFunctions.forEach(unsubscribe => unsubscribe());
    };
  }, [runningTaskIds.join(',')]); // 依赖运行中任务的ID列表

  // 验证所有任务的模型状态
  useEffect(() => {
    tasks.forEach(task => {
      if (!modelValidations[task.id]) {
        validateTaskModel(task.id);
      }
    });
  }, [tasks, modelValidations]);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const response = await evalscopeService.getTasks({
        status: statusFilter || undefined,
        skip: (current - 1) * pageSize,
        limit: pageSize
      });
      setTasks(response.tasks);
      setTotal(response.total);
    } catch (error) {
      message.error('加载任务列表失败');
    } finally {
      setLoading(false);
    }
  };

  // 验证任务模型状态
  const validateTaskModel = async (taskId: number) => {
    try {
      const validation = await evalscopeService.validateTaskModel(taskId);
      setModelValidations(prev => ({
        ...prev,
        [taskId]: validation
      }));
    } catch (error) {
      console.warn(`验证任务 ${taskId} 的模型失败:`, error);
    }
  };

  const handleDelete = async (taskId: number) => {
    const task = tasks.find(t => t.id === taskId);
    
    Modal.confirm({
      title: '确认删除任务',
      content: (
        <div>
          <p>您确定要删除以下任务吗？</p>
          <div style={{ 
            background: '#f5f5f5', 
            padding: '8px 12px', 
            borderRadius: '4px', 
            margin: '8px 0' 
          }}>
            <strong>任务名称:</strong> {task?.task_name}<br/>
            <strong>任务ID:</strong> #{taskId}<br/>
            <strong>状态:</strong> {getStatusTag(task?.status || 'unknown')}
          </div>
          <p style={{ color: '#ff4d4f', fontSize: '12px' }}>
            ⚠️ 此操作不可恢复，将永久删除任务及其相关数据
          </p>
        </div>
      ),
      okText: '确认删除',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        setDeletingTaskId(taskId);
        try {
          await evalscopeService.deleteTask(taskId);
          message.success('任务删除成功');
          loadTasks();
          // 如果删除的任务在选中列表中，也要移除
          setSelectedRows(prev => prev.filter(id => id !== taskId));
        } catch (error) {
          message.error('删除失败');
        } finally {
          setDeletingTaskId(null);
        }
      }
    });
  };

  // 批量删除失败任务
  const handleBatchDeleteFailed = async () => {
    const failedTasks = tasks.filter(task => task.status === 'failed');
    
    if (failedTasks.length === 0) {
      message.info('当前没有失败的任务');
      return;
    }

    Modal.confirm({
      title: `批量删除失败任务 (${failedTasks.length}个)`,
      content: (
        <div>
          <p>您确定要删除所有失败的任务吗？</p>
          <div style={{ 
            background: '#fff2f0', 
            border: '1px solid #ffccc7',
            borderRadius: '4px', 
            padding: '8px 12px',
            margin: '8px 0',
            maxHeight: '200px',
            overflowY: 'auto'
          }}>
            {failedTasks.map(task => (
              <div key={task.id} style={{ marginBottom: '4px' }}>
                #{task.id} - {task.task_name}
              </div>
            ))}
          </div>
          <p style={{ color: '#ff4d4f', fontSize: '12px' }}>
            ⚠️ 此操作不可恢复，将永久删除 {failedTasks.length} 个失败任务及其相关数据
          </p>
        </div>
      ),
      okText: '确认批量删除',
      cancelText: '取消',
      okType: 'danger',
      onOk: async () => {
        const hide = message.loading(`正在删除 ${failedTasks.length} 个失败任务...`, 0);
        try {
          // 并行删除所有失败任务
          await Promise.all(
            failedTasks.map(task => evalscopeService.deleteTask(task.id))
          );
          hide();
          message.success(`成功删除 ${failedTasks.length} 个失败任务`);
          loadTasks();
          setSelectedRows([]);
        } catch (error) {
          hide();
          message.error('批量删除失败，请重试');
        }
      }
    });
  };

  // 批量删除选中任务
  const handleBatchDeleteSelected = async () => {
    if (selectedRows.length === 0) {
      message.info('请先选择要删除的任务');
      return;
    }

    const selectedTasks = tasks.filter(task => selectedRows.includes(task.id));
    const deletableTasks = selectedTasks.filter(task => 
      ['completed', 'failed', 'cancelled', 'pending'].includes(task.status)
    );

    if (deletableTasks.length === 0) {
      message.warning('选中的任务中没有可删除的任务（只能删除非运行中的任务）');
      return;
    }

    Modal.confirm({
      title: `批量删除选中任务 (${deletableTasks.length}个)`,
      content: (
        <div>
          <p>您确定要删除选中的任务吗？</p>
          <div style={{ 
            background: '#f5f5f5', 
            borderRadius: '4px', 
            padding: '8px 12px',
            margin: '8px 0',
            maxHeight: '200px',
            overflowY: 'auto'
          }}>
            {deletableTasks.map(task => (
              <div key={task.id} style={{ 
                marginBottom: '4px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center'
              }}>
                <span>#{task.id} - {task.task_name}</span>
                {getStatusTag(task.status)}
              </div>
            ))}
          </div>
          {selectedTasks.length > deletableTasks.length && (
            <p style={{ color: '#faad14', fontSize: '12px' }}>
              ⚠️ 注意：运行中的任务不会被删除
            </p>
          )}
          <p style={{ color: '#ff4d4f', fontSize: '12px' }}>
            ⚠️ 此操作不可恢复，将永久删除选中的任务及其相关数据
          </p>
        </div>
      ),
      okText: '确认批量删除',
      cancelText: '取消', 
      okType: 'danger',
      onOk: async () => {
        const hide = message.loading(`正在删除 ${deletableTasks.length} 个任务...`, 0);
        try {
          await Promise.all(
            deletableTasks.map(task => evalscopeService.deleteTask(task.id))
          );
          hide();
          message.success(`成功删除 ${deletableTasks.length} 个任务`);
          loadTasks();
          setSelectedRows([]);
        } catch (error) {
          hide();
          message.error('批量删除失败，请重试');
        }
      }
    });
  };

  const handleCancel = async (taskId: number) => {
    try {
      await evalscopeService.cancelTask(taskId);
      message.success('任务已取消');
      loadTasks();
    } catch (error) {
      message.error('取消失败');
    }
  };

  // 生成智能的重试任务名称
  const generateRetryTaskName = (originalName: string): string => {
    // 检查是否已经包含重试信息（支持数字和纯文字两种格式）
    const retryMatchWithNumber = originalName.match(/^(.+?)\s*\(重试\s*(\d+)\)$/);
    const retryMatchWithoutNumber = originalName.match(/^(.+?)\s*\(重试\)$/);
    
    if (retryMatchWithNumber) {
      // 已经有数字重试标记，增加计数
      const baseName = retryMatchWithNumber[1];
      const currentCount = parseInt(retryMatchWithNumber[2]);
      return `${baseName} (重试 ${currentCount + 1})`;
    } else if (retryMatchWithoutNumber) {
      // 有纯文字重试标记，转换为数字格式
      const baseName = retryMatchWithoutNumber[1];
      return `${baseName} (重试 2)`;
    } else {
      // 没有重试标记，添加重试标记
      return `${originalName} (重试 1)`;
    }
  };

  const handleRetry = async (task: EvalTask) => {
    // 首先检查模型是否存在
    const validation = modelValidations[task.id];
    const modelExists = validation ? validation.model_exists : true;
    
    if (validation && !modelExists) {
      Modal.confirm({
        title: '模型不存在',
        content: (
          <div>
            <p>此任务使用的模型已不存在，无法重新评测。</p>
            <div style={{ 
              background: '#fff2f0', 
              border: '1px solid #ffccc7',
              borderRadius: '4px', 
              padding: '8px 12px',
              margin: '8px 0'
            }}>
              <strong>原模型:</strong> {validation.model_id}<br/>
              <strong>状态:</strong> <Tag color="red">不存在</Tag>
            </div>
            <p>请先在模型管理中添加此模型，或使用其他可用模型重新创建任务。</p>
          </div>
        ),
        okText: '知道了',
        cancelText: '查看模型管理',
        onCancel: () => {
          // 导航到模型管理页面
          navigate('/model-management');
        }
      });
      return;
    }
    
    const hide = message.loading('正在创建重新评测任务...', 0);
    try {
      // 先获取完整的任务详情（包含 extra_metadata）
      const taskDetail = await evalscopeService.getTask(task.id);
      console.log('获取到完整任务详情:', taskDetail);
      
      // 使用原任务的配置重新创建任务
      const newTask = await evalscopeService.createTask({
        task_name: generateRetryTaskName(task.task_name),
        model_id: taskDetail.model_id,
        datasets: taskDetail.datasets,
        model_args: taskDetail.model_args || {},
        dataset_args: taskDetail.dataset_args || {},
        generation_config: taskDetail.generation_config || {},
        eval_backend: taskDetail.eval_backend,
        eval_type: taskDetail.eval_type,
        user_model_config: taskDetail.extra_metadata?.user_model_config
      });
      
      hide();
      console.log('新任务已创建:', newTask);
      
      // 检查任务状态
      if (newTask.status === 'failed') {
        message.error(`任务创建失败: ${newTask.error_message || '未知错误'}`);
        return;
      }
      
      message.success(`任务 #${newTask.id} 已创建，正在执行评测...`);
      
      // 刷新列表
      await loadTasks();
      
      // 导航到新任务详情页
      navigate(`/evalscope/tasks/${newTask.id}`);
    } catch (error: any) {
      hide();
      console.error('重新评测失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '未知错误';
      message.error(`重新评测失败: ${errorMsg}`);
    }
  };

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; text: string }> = {
      pending: { color: 'default', text: '等待中' },
      running: { color: 'processing', text: '运行中' },
      completed: { color: 'success', text: '已完成' },
      failed: { color: 'error', text: '失败' },
      cancelled: { color: 'warning', text: '已取消' }
    };

    const config = statusMap[status] || statusMap.pending;
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '任务名称',
      dataIndex: 'task_name',
      key: 'task_name',
      width: 180,
      ellipsis: {
        showTitle: false,
      },
      render: (text: string) => (
        <Tooltip title={text} placement="topLeft">
          <span style={{
            display: 'block',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap'
          }}>
            {text}
          </span>
        </Tooltip>
      )
    },
    {
      title: '模型',
      dataIndex: 'model_id',
      key: 'model_id',
      width: 220,
      ellipsis: {
        showTitle: false,
      },
      render: (text: string, record: EvalTask) => {
        const validation = modelValidations[record.id];
        const modelExists = validation ? validation.model_exists : true; // 未验证时默认存在，验证后以结果为准
        
        return (
          <Space direction="vertical" size={0}>
            <Tooltip title={text} placement="topLeft">
              <span style={{ 
                display: 'block',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: '100%'
              }}>
                {text}
              </span>
            </Tooltip>
            {validation && !modelExists && (
              <Tag color="red">
                模型不存在
              </Tag>
            )}
          </Space>
        );
      }
    },
    {
      title: '数据集',
      dataIndex: 'datasets',
      key: 'datasets',
      width: 160,
      render: (datasets: string[]) => (
        <div style={{ maxWidth: '100%' }}>
          {datasets.length <= 2 ? (
            <Space wrap size={[4, 4]}>
              {datasets.map(dataset => (
                <Tag key={dataset} color="blue" style={{ fontSize: '12px', margin: '1px' }}>
                  {dataset}
                </Tag>
              ))}
            </Space>
          ) : (
            <Tooltip 
              title={datasets.join(', ')} 
              placement="topLeft"
              overlayStyle={{ maxWidth: '300px' }}
            >
              <Space wrap size={[4, 4]}>
                {datasets.slice(0, 2).map(dataset => (
                  <Tag key={dataset} color="blue" style={{ fontSize: '12px', margin: '1px' }}>
                    {dataset}
                  </Tag>
                ))}
                <Tag color="default" style={{ fontSize: '12px', margin: '1px' }}>
                  +{datasets.length - 2}
                </Tag>
              </Space>
            </Tooltip>
          )}
        </div>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status)
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString()
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      fixed: 'right' as const,
      render: (record: EvalTask) => (
        <Space size="small" wrap>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/evalscope/tasks/${record.id}`)}
            style={{ padding: '4px 6px' }}
          >
            查看
          </Button>
          {/* 取消按钮：运行中和等待中的任务都可以取消 */}
          {(['running', 'pending'].includes(record.status)) && (
            <Button
              type="link"
              size="small"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancel(record.id)}
              style={{ padding: '4px 6px' }}
            >
              取消
            </Button>
          )}
          
          {/* 重新评测按钮：失败和已取消的任务可以重新评测 */}
          {(['failed', 'cancelled'].includes(record.status)) && (
            <>
              {(() => {
                const validation = modelValidations[record.id];
                const modelExists = validation ? validation.model_exists : true;
                const canRetry = modelExists; // 只要模型存在就可以重试
                
                return (
                  <Tooltip 
                    title={!canRetry ? '模型不存在，无法重新评测' : '重新执行评测任务'}
                  >
                    <Button
                      type="link"
                      size="small"
                      icon={<RedoOutlined />}
                      onClick={() => handleRetry(record)}
                      disabled={!canRetry}
                      style={{
                        opacity: !canRetry ? 0.5 : 1,
                        padding: '4px 6px'
                      }}
                    >
                      重新评测
                    </Button>
                  </Tooltip>
                );
              })()}
            </>
          )}
          
          {/* 删除按钮：非运行中的任务都可以删除 */}
          {(['completed', 'failed', 'cancelled', 'pending'].includes(record.status)) && (
            <Tooltip title="删除任务及其相关数据">
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                loading={deletingTaskId === record.id}
                onClick={() => handleDelete(record.id)}
                style={{
                  color: record.status === 'failed' ? '#ff4d4f' : undefined,
                  fontWeight: record.status === 'failed' ? 'bold' : 'normal',
                  padding: '4px 6px'
                }}
              >
                删除
              </Button>
            </Tooltip>
          )}
        </Space>
      )
    }
  ];

  // 检查是否有运行中的任务
  const runningTasks = tasks.filter(task => task.status === 'running');
  const hasRunningTasks = runningTasks.length > 0;

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        {/* 运行中任务提醒 */}
        {hasRunningTasks && (
          <Alert
            message={`🔥 当前有 ${runningTasks.length} 个评测任务正在运行`}
            description={
              <div>
                <p>⚡ <strong>性能提醒：</strong>评测任务正在占用大量系统资源，可能导致电脑运行缓慢。</p>
                <p>💡 <strong>建议：</strong>避免同时启动多个评测任务，等待当前任务完成后再创建新任务。</p>
                <div style={{ marginTop: 8 }}>
                  <Space>
                    {runningTasks.map(task => (
                      <Button
                        key={task.id}
                        size="small"
                        type="link"
                        onClick={() => navigate(`/evalscope/tasks/${task.id}`)}
                      >
                        查看任务 #{task.id}
                      </Button>
                    ))}
                  </Space>
                </div>
              </div>
            }
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>EvalScope 评测任务</h2>
          <Space>
            <Space>
              <Button 
                icon={<SwapOutlined />}
                onClick={() => navigate('/evalscope/compare')}
              >
                模型对比
              </Button>
              <Button 
                type="primary" 
                icon={<PlusOutlined />}
                onClick={() => navigate('/evalscope/tasks/create')}
              >
                创建新任务
              </Button>
            </Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={loadTasks}
            >
              刷新
            </Button>
          </Space>
        </div>

        {/* 批量操作工具栏 */}
        {(tasks.some(task => task.status === 'failed') || selectedRows.length > 0) && (
          <div style={{ 
            marginBottom: 16, 
            padding: '12px 16px',
            background: '#f8f9fa',
            borderRadius: '6px',
            border: '1px solid #e9ecef'
          }}>
            <Space wrap>
              {tasks.some(task => task.status === 'failed') && (
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  onClick={handleBatchDeleteFailed}
                >
                  删除所有失败任务 ({tasks.filter(task => task.status === 'failed').length})
                </Button>
              )}
              {selectedRows.length > 0 && (
                <Button
                  danger
                  icon={<DeleteOutlined />}
                  onClick={handleBatchDeleteSelected}
                >
                  删除选中任务 ({selectedRows.length})
                </Button>
              )}
              {selectedRows.length > 0 && (
                <span style={{ color: '#666', fontSize: '12px' }}>
                  已选择 {selectedRows.length} 个任务
                </span>
              )}
            </Space>
          </div>
        )}

        <div style={{ marginBottom: 16, display: 'flex', gap: 16 }}>
          <Select
            style={{ width: 120 }}
            placeholder="状态筛选"
            allowClear
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'pending', label: '等待中' },
              { value: 'running', label: '运行中' },
              { value: 'completed', label: '已完成' },
              { value: 'failed', label: '失败' },
              { value: 'cancelled', label: '已取消' }
            ]}
          />
        </div>

        <Table
          columns={columns}
          dataSource={tasks}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1200 }}
          rowSelection={{
            type: 'checkbox',
            selectedRowKeys: selectedRows,
            onChange: (selectedRowKeys) => {
              setSelectedRows(selectedRowKeys as number[]);
            },
            getCheckboxProps: (record) => ({
              // 只允许选择可删除的任务（非运行中的任务）
              disabled: !['completed', 'failed', 'cancelled', 'pending'].includes(record.status),
            }),
          }}
          pagination={{
            current,
            pageSize,
            total,
            onChange: setCurrent,
            showSizeChanger: false,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
          }}
        />
      </Card>
    </div>
  );
};

export default TaskListPage;
