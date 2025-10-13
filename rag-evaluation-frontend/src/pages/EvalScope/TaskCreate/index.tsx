/**
 * 创建EvalScope评测任务页面
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Form,
  Input,
  Button,
  Select,
  Card,
  Steps,
  message,
  Space,
  InputNumber,
  Tag,
  Divider,
  Tooltip,
  Alert
} from 'antd';
import {
  RocketOutlined,
  SettingOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import axiosInstance from '../../../utils/axios';
import type { TaskCreateRequest, EvalTask } from '../../../types/evalscope.types';
import { evalscopeService } from '../../../services/evalscope.service';
import { generateTimeEstimateReport, checkTimeWarning } from '../../../utils/evalTimeEstimator';
import { ConfigManager } from '../../../utils/configManager';
import { authService } from '../../../services/auth.service';
import './ModelSelect.css';

const { Step } = Steps;
const { TextArea } = Input;
const { Option } = Select;

interface BenchmarkInfo {
  id: string;
  name: string;
  description: string;
  category: string;
  samples?: number;
  metrics: string[];
  language?: string;
}

const TaskCreatePage: React.FC = () => {
  const [current, setCurrent] = useState(0);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([]);
  const [userModels, setUserModels] = useState<any[]>([]);
  const [unifiedModels, setUnifiedModels] = useState<any[]>([]);
  const [timeEstimate, setTimeEstimate] = useState<string>('');
  const [timeWarning, setTimeWarning] = useState<{isLong: boolean; warning: string; suggestions: string[]}>({
    isLong: false,
    warning: '',
    suggestions: []
  });
  const navigate = useNavigate();
  const configManager = ConfigManager.getInstance();
  
  // 任务名称序号计数器
  const [taskNameCounter, setTaskNameCounter] = useState(1);

  // 获取模型显示名称
  const getModelDisplayName = (modelId: string) => {
    if (!modelId) return '';
    
    // 如果是 user_config_ 开头的，查找实际模型名称
    if (modelId.startsWith('user_config_')) {
      const configId = modelId.replace('user_config_', '');
      
      // 先从 userModels 查找
      let userModel = userModels.find(m => m.id === configId);
      
      // 如果没找到，从 unifiedModels 查找
      if (!userModel) {
        const unifiedModel = unifiedModels.find(m => m.id === modelId);
        if (unifiedModel) {
          return unifiedModel.name || unifiedModel.display_name || modelId;
        }
      } else {
        return userModel.modelName || userModel.name || modelId;
      }
    }
    
    // 如果是 config: 开头的
    if (modelId.startsWith('config:')) {
      const configId = modelId.replace('config:', '');
      const userModel = userModels.find(m => m.id === configId);
      if (userModel) {
        return userModel.modelName || userModel.name || modelId;
      }
    }
    
    // 预设模型，直接返回模型ID（去掉命名空间）
    if (modelId.includes('/')) {
      return modelId.split('/').pop() || modelId;
    }
    
    return modelId;
  };

  // 自动生成任务名称
  const autoGenerateTaskName = () => {
    const modelId = form.getFieldValue('model_id');
    const evalBackend = form.getFieldValue('eval_backend') || 'Native';
    
    // 获取模型显示名称
    const modelName = getModelDisplayName(modelId);
    
    // 构建任务名称
    let taskName = '';
    if (modelName) {
      taskName = `${modelName}`;
    } else {
      taskName = '评测任务';
    }
    
    // 添加数据集信息（使用状态中的selectedBenchmarks）
    if (selectedBenchmarks.length > 0) {
      if (selectedBenchmarks.length <= 3) {
        taskName += `_${selectedBenchmarks.join('+')}`;
      } else {
        taskName += `_${selectedBenchmarks.length}个数据集`;
      }
    }
    
    // 添加序号后缀
    taskName += `_${taskNameCounter}`;
    
    // 递增计数器
    setTaskNameCounter(prev => prev + 1);
    
    // 设置表单值和状态
    form.setFieldsValue({ task_name: taskName });
    setFormData(prev => ({ ...prev, task_name: taskName }));
  };

  // 模型ID格式验证函数
  const validateModelId = (modelId: string, evalType: string): { isValid: boolean; message?: string } => {
    if (!modelId || modelId.trim() === '') {
      return { isValid: false, message: '模型ID不能为空' };
    }
    
    if (modelId === 'model') {
      return { isValid: false, message: '模型ID不能为"model"，请选择具体的模型' };
    }
    
    // 对于本地模型，检查namespace/name格式
    if (evalType === 'llm_ckpt' && !modelId.includes('/') && modelId !== 'qwen-plus-2025-09-11') {
      return { 
        isValid: false, 
        message: `本地模型需要使用namespace/name格式，如"Qwen/Qwen2.5-0.5B-Instruct"，当前格式："${modelId}"不正确` 
      };
    }
    
    return { isValid: true };
  };
  
  // 使用state存储表单值（解决多步骤问题）
  const [formData, setFormData] = useState({
    model_id: '',
    task_name: '',
    model_args: '',
    generation_config: '',
    eval_backend: 'Native',
    limit: undefined as number | undefined
  });

  // 加载Benchmark列表和用户模型配置
  useEffect(() => {
    loadBenchmarks();
    loadUserModels();
    loadUnifiedModels();
  }, []);

  // 监听表单变化，更新时间预估
  useEffect(() => {
    updateTimeEstimate();
  }, [selectedBenchmarks, formData.limit, formData.model_id]);

  // 监听模型和数据集变化，自动生成任务名称
  useEffect(() => {
    const modelId = form.getFieldValue('model_id');
    if (modelId && selectedBenchmarks.length > 0) {
      autoGenerateTaskName();
    }
  }, [selectedBenchmarks, formData.model_id]);

  const loadBenchmarks = async () => {
    try {
      const response = await evalscopeService.getBenchmarks();
      setBenchmarks(response.benchmarks);
    } catch (error) {
      message.error('加载Benchmark列表失败');
    }
  };

  const loadUserModels = async () => {
    try {
      const models = await configManager.getAllConfigs('model');
      setUserModels(models);
    } catch (error) {
      console.error('加载用户模型配置失败:', error);
      // 静默失败，不显示错误信息
    }
  };

  const loadUnifiedModels = async () => {
    try {
      // 添加时间戳防止缓存
      const timestamp = new Date().getTime();
      
      try {
        // 先检查是否有认证信息
        const token = authService.getToken();
        if (token) {
          console.log('尝试使用认证接口获取模型列表');
          const response = await axiosInstance.get(`/v1/unified-models/all?t=${timestamp}`);
          setUnifiedModels(response.data.models || []);
          console.log('加载的认证模型:', response.data.models?.map(m => `${m.display_name} (${m.name})`));
          return; // 成功获取，直接返回
        } else {
          console.log('未找到认证token，使用测试接口');
        }
      } catch (error) {
        // 如果是401错误，不要让axios拦截器处理，而是静默降级
        if (error.response?.status === 401) {
          console.log('认证失败，降级到测试接口（不清除认证信息）');
        } else {
          console.log('认证接口失败，降级到测试接口:', error.message);
        }
      }
      
      // 降级到测试接口（不需要认证）
      try {
        console.log('使用测试接口获取模型列表');
        const testResponse = await fetch(`/api/v1/unified-models/test/available?t=${timestamp}`);
        if (testResponse.ok) {
          const testData = await testResponse.json();
          setUnifiedModels(testData.models || []);
          console.log('测试模型:', testData.models?.map(m => `${m.display_name} (${m.name})`));
        } else {
          console.log('测试接口也失败了:', testResponse.status, testResponse.statusText);
          setUnifiedModels([]);
        }
      } catch (testError) {
        console.error('测试接口异常:', testError);
        setUnifiedModels([]);
      }
      
    } catch (error) {
      console.error('加载统一模型列表失败:', error);
      setUnifiedModels([]);
    }
  };

  // 计算时间预估
  const updateTimeEstimate = () => {
    const datasets = selectedBenchmarks;
    const limit = formData.limit;
    const modelType = formData.model_id.includes('api') || formData.model_id.includes('gpt') || formData.model_id.includes('qwen') ? 'api' : 'local';
    
    if (datasets.length > 0) {
      const report = generateTimeEstimateReport(datasets, modelType, limit, datasets.length > 1);
      setTimeEstimate(report);
      
      const warning = checkTimeWarning(datasets, modelType, limit);
      setTimeWarning(warning);
    } else {
      setTimeEstimate('');
      setTimeWarning({ isLong: false, warning: '', suggestions: [] });
    }
  };

  // 保存当前步骤的表单值
  const saveCurrentStep = () => {
    const values = form.getFieldsValue();
    setFormData(prev => ({...prev, ...values}));
  };

  // 下一步
  const handleNext = () => {
    saveCurrentStep();
    setCurrent(current + 1);
  };

  // 上一步
  const handlePrev = () => {
    saveCurrentStep();
    setCurrent(current - 1);
  };

  // 提交任务
  const handleSubmit = async () => {
    try {
      setLoading(true);

      // 保存最后一步的值
      saveCurrentStep();
      
      // 获取所有值（包括当前表单和之前保存的state）
      const currentValues = form.getFieldsValue();
      const allValues = {...formData, ...currentValues};
      
      
      // 验证必填项
      if (!allValues.model_id) {
        message.error('❌ 请在步骤1中选择模型');
        setLoading(false);
        setCurrent(0);
        return;
      }
      if (selectedBenchmarks.length === 0) {
        message.error('❌ 请在步骤2中选择至少一个Benchmark');
        setLoading(false);
        setCurrent(1);
        return;
      }
      if (!allValues.task_name) {
        message.error('❌ 请在步骤3中输入任务名称');
        setLoading(false);
        setCurrent(2);
        return;
      }

      // 处理模型配置
      let modelId = allValues.model_id;
      let modelConfig = null;
      
      if (allValues.model_id?.startsWith('config:') || allValues.model_id?.startsWith('user_config_')) {
        // 用户选择了已配置的模型
        const configId = allValues.model_id.replace('config:', '').replace('user_config_', '');
        
        console.log('🔍 查找模型配置:', { 
          originalId: allValues.model_id, 
          configId,
          userModelsCount: userModels.length,
          unifiedModelsCount: unifiedModels.length
        });
        
        // 先从 userModels 查找
        let userModel = userModels.find(m => m.id === configId);
        
        // 如果没找到，从 unifiedModels 查找
        if (!userModel) {
          console.log('⚠️ 未在 userModels 中找到，尝试从 unifiedModels 查找');
          const unifiedModel = unifiedModels.find(m => m.id === allValues.model_id);
          if (unifiedModel) {
            console.log('✅ 在 unifiedModels 中找到模型:', unifiedModel);
            // 将 unifiedModel 转换为 userModel 格式
            // 注意：unifiedModel.config 包含了所有配置信息
            userModel = {
              id: configId,
              type: unifiedModel.model_type || 'api',
              baseUrl: unifiedModel.config?.api_url || unifiedModel.config?.base_url,
              apiKey: unifiedModel.config?.api_key,
              modelName: unifiedModel.name,  // name字段是实际的模型名称
              additionalParams: unifiedModel.config?.extra_metadata || unifiedModel.config?.additional_params || {}
            };
            console.log('📝 转换后的用户模型配置:', userModel);
          } else {
            console.error('❌ 在 unifiedModels 中也未找到模型，可用的模型ID:', unifiedModels.map(m => m.id));
          }
        } else {
          console.log('✅ 在 userModels 中找到模型:', userModel);
        }
        
        if (userModel) {
          modelConfig = {
            type: userModel.type,
            base_url: userModel.baseUrl,
            api_key: userModel.apiKey,
            model_name: userModel.modelName,
            additional_params: userModel.additionalParams || {}
          };
          modelId = userModel.modelName; // 使用配置中的模型名称
          
          console.log('✅ 解析出的模型配置:', { modelId, type: modelConfig.type, base_url: modelConfig.base_url });
          
          // 验证模型ID格式
          if (modelConfig.type !== 'api' && modelId && !modelId.includes('/') && modelId !== 'qwen-plus-2025-09-11') {
            console.warn(`本地模型ID格式可能不正确: ${modelId}，建议使用namespace/name格式`);
          }
        } else {
          // 找不到用户配置
          message.error({
            content: (
              <div>
                <p>❌ 无法找到模型配置</p>
                <p><strong>错误：</strong>模型配置ID "{configId}" 不存在或已被删除</p>
                <p><strong>解决方案：</strong></p>
                <p>1. 前往【系统配置 → 大模型配置】检查配置是否存在</p>
                <p>2. 重新选择可用的模型配置</p>
                <p>3. 或创建新的模型配置</p>
              </div>
            ),
            duration: 8
          });
          setLoading(false);
          return;
        }
      }

      // 自动判断eval_type
      let evalType = 'llm_ckpt'; // 默认为llm_ckpt（本地模型）
      
      // 如果是已配置的模型，根据配置类型决定
      if (modelConfig) {
        if (modelConfig.type === 'api' || modelConfig.base_url) {
          evalType = 'openai_api';
          
          // 验证API配置是否完整
          if (!modelConfig.api_key) {
            message.error('❌ 选择的模型配置缺少API密钥，请先在系统配置中完善模型配置');
            setLoading(false);
            return;
          }
        }
      } else {
        // 如果模型名包含特定的API服务标识，设置为service
        const apiModelPatterns = [
          'qwen-plus', 'qwen-max', 'qwen-turbo',
          'gpt-', 'claude-', 'gemini-',
          'api', 'service'
        ];
        
        if (apiModelPatterns.some(pattern => modelId.toLowerCase().includes(pattern))) {
          evalType = 'openai_api';
          
          // 如果是API模型但没有用户配置，给出明确提示
          message.error({
            content: (
              <div>
                <p>❌ 检测到您选择了API模型但未配置相关信息</p>
                <p><strong>解决方案：</strong></p>
                <p>1. 前往【系统配置 → 大模型配置】添加模型配置</p>
                <p>2. 配置完成后重新选择对应的模型配置项</p>
                <p>3. 或者选择本地模型进行评测</p>
              </div>
            ),
            duration: 8
          });
          setLoading(false);
          return;
        }
      }

      // 验证模型ID格式
      console.log('🔍 准备验证模型ID:', { modelId, evalType, hasModelConfig: !!modelConfig });
      const validation = validateModelId(modelId, evalType);
      console.log('📋 验证结果:', validation);
      if (!validation.isValid) {
        message.error({
          content: (
            <div>
              <p>❌ 模型配置验证失败</p>
              <p><strong>错误：</strong>{validation.message}</p>
              <p><strong>建议：</strong></p>
              <p>• 对于本地模型，使用格式如：Qwen/Qwen2.5-0.5B-Instruct</p>
              <p>• 对于API模型，请先在【系统配置】中配置模型信息</p>
            </div>
          ),
          duration: 8
        });
        setLoading(false);
        return;
      }

      // 构建任务数据
      const taskData: TaskCreateRequest = {
        task_name: allValues.task_name,
        model_id: modelId,
        datasets: selectedBenchmarks,
        model_args: allValues.model_args ? JSON.parse(allValues.model_args) : {},
        generation_config: allValues.generation_config ? JSON.parse(allValues.generation_config) : {},
        eval_backend: allValues.eval_backend || 'Native',
        eval_type: evalType,
        limit: allValues.limit,
        // 添加用户模型配置
        ...(modelConfig && { user_model_config: modelConfig })
      };

      
      // 显示确认对话框：选择执行方式
      const useSync = window.confirm(
        '🚀 真实评测确认\n\n' +
        '点击"确定"：立即执行真实评测（创建后跳转到监控页面）\n' +
        '点击"取消"：后台异步执行（需要Celery配置）\n\n' +
        timeEstimate + '\n\n' +
        (timeWarning.isLong ? timeWarning.warning + '\n\n' : '') +
        '⚠️ 评测会占用大量CPU和内存资源，建议关闭不必要的程序'
      );
      
      // 显示短暂的创建中提示
      const loadingMsg = message.loading('正在创建评测任务...', 2);
      
      let task;
      try {
        if (useSync) {
          // 同步模式：创建任务并开始执行
          task = await evalscopeService.createTaskSync(taskData);
        } else {
          // 异步模式：仅创建任务
          task = await evalscopeService.createTask(taskData);
        }
        
        console.log('✅ 任务创建成功，返回的task对象:', task);
        console.log('✅ 任务ID:', task?.id);
        
        // 销毁loading消息
        loadingMsg();
        
        // 检查task和task.id是否存在
        if (!task || !task.id) {
          message.error('任务创建成功但无法获取任务ID，请刷新页面查看任务列表');
          console.error('❌ 任务对象或ID缺失:', task);
          setLoading(false);
          return;
        }
        
        // 显示成功消息
        const successMsg = useSync 
          ? `✅ 任务已创建并开始执行！任务ID: ${task.id}`
          : `✅ 任务已提交到后台执行！任务ID: ${task.id}`;
        
        message.success(successMsg);
        console.log(successMsg);
        
        // 立即跳转到任务监控页面
        console.log('🔄 准备跳转到:', `/evalscope/tasks/${task.id}`);
        console.log('🚀 开始执行跳转');
        
        // 直接跳转，不使用setTimeout
        navigate(`/evalscope/tasks/${task.id}`, { replace: false });
        
      } catch (error) {
        loadingMsg();
        throw error;
      }

    } catch (error: any) {
      console.error('❌ 创建任务错误:', error);
      
      if (error.response) {
        const detail = error.response.data?.detail;
        if (typeof detail === 'string') {
          message.error(`创建失败: ${detail}`);
        } else if (Array.isArray(detail)) {
          const errors = detail.map((err: any) => err.msg).join(', ');
          message.error(`数据验证错误: ${errors}`);
        } else {
          message.error(`HTTP ${error.response.status}: ${error.response.statusText}`);
        }
      } else if (error.name === 'SyntaxError') {
        message.error('JSON配置格式错误，请检查参数配置');
      } else if (error.message) {
        message.error(`创建失败: ${error.message}`);
      } else {
        message.error('创建任务失败，请查看控制台了解详情');
      }
      
      setLoading(false);
    } finally {
      // 确保loading状态总是被重置
      // 注意：只有在没有成功跳转的情况下才需要重置loading
      // 如果成功跳转了，组件会被卸载，loading状态就无关紧要了
    }
  };

  // 步骤内容
  const steps = [
    {
      title: '选择模型',
      icon: <RocketOutlined />,
      content: (
        <Card>
          <Form.Item
            name="model_id"
            label={
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                选择模型
                <Button 
                  type="link" 
                  size="small"
                  icon={<ReloadOutlined />}
                  onClick={loadUnifiedModels}
                  style={{ padding: 0, height: 'auto' }}
                >
                  刷新
                </Button>
              </div>
            }
            rules={[{ required: true, message: '请选择模型' }]}
            tooltip="可以选择已配置的模型或输入ModelScope/HuggingFace模型ID"
          >
            <Select
              showSearch
              placeholder="选择模型进行评测"
              allowClear
              style={{ width: '100%' }}
              dropdownClassName="model-select-dropdown"
              filterOption={(input, option) => {
                const searchText = input.toLowerCase();
                return (option?.label ?? '').toLowerCase().includes(searchText);
              }}
            >
              {/* 直接显示统一管理的所有模型 */}
              {unifiedModels
                .sort((a, b) => {
                  // 收藏的模型优先
                  if (a.is_favorite && !b.is_favorite) return -1;
                  if (!a.is_favorite && b.is_favorite) return 1;
                  // 然后按使用次数排序
                  return (b.usage_count || 0) - (a.usage_count || 0);
                })
                .map(model => (
                  <Select.Option 
                    key={model.id} 
                    value={model.id}
                    label={`${model.display_name} ${model.model_type === 'local' ? '[本地]' : model.model_type === 'api' ? '[API]' : '[云端]'}`}
                  >
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      padding: '4px 0'
                    }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ 
                          color: '#262626',
                          fontSize: '14px',
                          fontWeight: '500',
                          marginBottom: '2px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }}>
                          {model.display_name}
                        </div>
                        {(model.model_family || model.model_size) && (
                          <div style={{ 
                            fontSize: '12px', 
                            color: '#8c8c8c'
                          }}>
                            {model.model_family && `${model.model_family}`}
                            {model.model_family && model.model_size && ' • '}
                            {model.model_size && `${model.model_size}`}
                          </div>
                        )}
                      </div>
                      <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '6px',
                        flexShrink: 0,
                        marginLeft: '12px'
                      }}>
                        <span style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          fontWeight: '500',
                          backgroundColor: model.model_type === 'local' ? '#f6ffed' : '#e6f7ff',
                          color: model.model_type === 'local' ? '#52c41a' : '#1890ff',
                          border: `1px solid ${model.model_type === 'local' ? '#b7eb8f' : '#91d5ff'}`
                        }}>
                          {model.model_type === 'local' ? '本地' : 'API'}
                        </span>
                        {model.is_favorite && (
                          <span style={{ color: '#fadb14', fontSize: '14px' }}>⭐</span>
                        )}
                      </div>
                    </div>
                  </Select.Option>
                ))}
              
              {/* 如果没有统一管理的模型，显示预设模型 */}
              {unifiedModels.length === 0 && (
                <>
                  <Select.Option value="Qwen/Qwen2.5-0.5B-Instruct">
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      padding: '4px 0'
                    }}>
                      <div>
                        <div style={{ color: '#262626', fontSize: '14px', fontWeight: '500' }}>
                          Qwen2.5-0.5B-Instruct
                        </div>
                        <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
                          推荐测试模型
                        </div>
                      </div>
                      <span style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontWeight: '500',
                        backgroundColor: '#f6ffed',
                        color: '#52c41a',
                        border: '1px solid #b7eb8f'
                      }}>
                        本地
                      </span>
                    </div>
                  </Select.Option>
                  <Select.Option value="Qwen/Qwen2.5-7B-Instruct">
                    <div style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between',
                      padding: '4px 0'
                    }}>
                      <div style={{ color: '#262626', fontSize: '14px', fontWeight: '500' }}>
                        Qwen2.5-7B-Instruct
                      </div>
                      <span style={{
                        fontSize: '11px',
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontWeight: '500',
                        backgroundColor: '#f6ffed',
                        color: '#52c41a',
                        border: '1px solid #b7eb8f'
                      }}>
                        本地
                      </span>
                    </div>
                  </Select.Option>
                </>
              )}
            </Select>
          </Form.Item>
          
          {/* 显示选中模型的详细信息 */}
          {(() => {
            const modelId = form.getFieldValue('model_id');
            if (!modelId) return null;
            
            // 查找统一管理的模型
            const unifiedModel = unifiedModels.find(m => m.id === modelId);
            if (unifiedModel) {
              return (
            <div style={{
                  background: '#e6f7ff',
                  border: '1px solid #91d5ff',
              borderRadius: 6,
              padding: 12,
              marginBottom: 16
            }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: '#1890ff', display: 'flex', alignItems: 'center', gap: 8 }}>
                    🎯 使用统一管理的模型
                    {unifiedModel.is_favorite && <span style={{ color: '#fadb14' }}>⭐</span>}
                  </div>
                  <div style={{ fontSize: 13, lineHeight: 1.6 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px' }}>
                      <div><strong>模型名称:</strong> {unifiedModel.display_name}</div>
                      <div><strong>模型类型:</strong> 
                        <span style={{
                          marginLeft: 4,
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '3px',
                          backgroundColor: unifiedModel.model_type === 'local' ? '#f6ffed' : '#e6f7ff',
                          color: unifiedModel.model_type === 'local' ? '#52c41a' : '#1890ff'
                        }}>
                          {unifiedModel.model_type === 'local' ? '本地模型' : 
                           unifiedModel.model_type === 'api' ? 'API模型' : 
                           unifiedModel.model_type === 'cloud' ? '云端模型' : unifiedModel.model_type}
                        </span>
                      </div>
                      {unifiedModel.model_family && (
                        <div><strong>模型系列:</strong> {unifiedModel.model_family}</div>
                      )}
                      {unifiedModel.model_size && (
                        <div><strong>模型大小:</strong> {unifiedModel.model_size}</div>
                      )}
                      {unifiedModel.capabilities && unifiedModel.capabilities.length > 0 && (
                        <div style={{ gridColumn: '1 / -1' }}>
                          <strong>支持能力:</strong> 
                          <div style={{ marginTop: 4 }}>
                            {unifiedModel.capabilities.map(cap => (
                              <span key={cap} style={{
                                display: 'inline-block',
                                margin: '2px 4px 2px 0',
                                fontSize: '11px',
                                padding: '2px 6px',
                                borderRadius: '3px',
                                backgroundColor: '#fff7e6',
                                color: '#fa8c16',
                                border: '1px solid #ffd591'
                              }}>
                                {cap}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {unifiedModel.usage_count > 0 && (
                        <div><strong>使用次数:</strong> {unifiedModel.usage_count} 次</div>
                      )}
                      {unifiedModel.quality_rating && (
                        <div><strong>质量评分:</strong> {unifiedModel.quality_rating}/10</div>
                      )}
                    </div>
                  </div>
                </div>
              );
            }
            
            // 查找旧版配置的模型
            if (modelId.startsWith('config:') || modelId.startsWith('user_config_')) {
              const configId = modelId.replace('config:', '').replace('user_config_', '');
                const model = userModels.find(m => m.id === configId);
                if (!model) return null;
                
                return (
            <div style={{
              background: '#f6ffed',
              border: '1px solid #b7eb8f',
              borderRadius: 6,
              padding: 12,
              marginBottom: 16
            }}>
                    <div style={{ fontWeight: 600, marginBottom: 8, color: '#52c41a' }}>
                    ⚙️ 使用旧版配置的模型
                    </div>
                    <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                      <div><strong>配置名称:</strong> {model.name}</div>
                      <div><strong>模型类型:</strong> {model.type}</div>
                      <div><strong>API地址:</strong> {model.baseUrl}</div>
                      <div><strong>模型名称:</strong> {model.modelName}</div>
                    </div>
                  </div>
                );
            }
            
            // 预设模型
            if (modelId && !modelId.startsWith('config:') && !modelId.startsWith('user_config_')) {
              return (
                <div style={{
                  background: '#fff7e6',
                  border: '1px solid #ffd591',
                  borderRadius: 6,
                  padding: 12,
                  marginBottom: 16
                }}>
                  <div style={{ fontWeight: 600, marginBottom: 8, color: '#fa8c16' }}>
                    📋 使用预设模型
            </div>
                  <div style={{ fontSize: 13, lineHeight: 1.5 }}>
                    <div><strong>模型ID:</strong> {modelId}</div>
                    <div style={{ color: '#8c8c8c', marginTop: 4 }}>
                      将从ModelScope/HuggingFace自动下载和加载此模型
                    </div>
                  </div>
                </div>
              );
            }
            
            return null;
              })()}


          {unifiedModels.length === 0 && userModels.length === 0 && (
            <div style={{
              background: '#fff7e6',
              border: '1px solid #ffd591',
              borderRadius: 6,
              padding: 12,
              marginBottom: 16
            }}>
              <div style={{ color: '#fa8c16', fontSize: 13 }}>
                💡 提示：您还没有配置任何模型。可以在 
                <strong> 大模型管理 </strong> 
                中同步现有模型或添加新模型。
              </div>
            </div>
          )}

          <Form.Item
            name="model_args"
            label="模型参数"
            tooltip="JSON格式，例如: {&quot;revision&quot;: &quot;master&quot;, &quot;precision&quot;: &quot;torch.float16&quot;}"
          >
            <TextArea
              rows={4}
              placeholder='{"revision": "master", "precision": "torch.float16", "device_map": "auto"}'
            />
          </Form.Item>
        </Card>
      )
    },
    {
      title: '选择Benchmark',
      icon: <FileTextOutlined />,
      content: (
        <Card>
          <div style={{ marginBottom: 16 }}>
            <Space>
              <span>已选择:</span>
              <Tag color="blue">{selectedBenchmarks.length} 个Benchmark</Tag>
            </Space>
          </div>

          <Select
            mode="multiple"
            style={{ width: '100%' }}
            placeholder="选择评测数据集"
            value={selectedBenchmarks}
            onChange={setSelectedBenchmarks}
            optionLabelProp="label"
            maxTagCount="responsive"
            dropdownStyle={{ maxWidth: '600px' }}
          >
            {benchmarks.map((benchmark) => (
              <Option
                key={benchmark.name}
                value={benchmark.name}
                label={benchmark.name}
              >
                <Tooltip
                  title={benchmark.description}
                  placement="topLeft"
                  overlayStyle={{ maxWidth: '400px' }}
                >
                  <div style={{ 
                    display: 'flex', 
                    justifyContent: 'space-between', 
                    alignItems: 'flex-start',
                    gap: '12px',
                    maxWidth: '100%'
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                        {benchmark.name}
                      </div>
                      <div style={{ 
                        fontSize: '12px', 
                        color: '#888',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        maxWidth: '300px'
                      }}>
                        {benchmark.description}
                      </div>
                    </div>
                    <div style={{ flexShrink: 0 }}>
                      <Space size={4}>
                        <Tag color="green" style={{ margin: 0, fontSize: '11px' }}>
                          {benchmark.category}
                        </Tag>
                        <Tag style={{ margin: 0, fontSize: '11px' }}>
                          {benchmark.language}
                        </Tag>
                      </Space>
                    </div>
                  </div>
                </Tooltip>
              </Option>
            ))}
          </Select>

          <Divider />

          <Space>
            <Button
              size="small"
              onClick={() => setSelectedBenchmarks(['mmlu', 'gsm8k', 'arc'])}
            >
              推荐套餐1: 通用能力
            </Button>
            <Button
              size="small"
              onClick={() => setSelectedBenchmarks(['gsm8k', 'math_500', 'competition_math'])}
            >
              推荐套餐2: 数学推理
            </Button>
          </Space>
        </Card>
      )
    },
    {
      title: '评测配置',
      icon: <SettingOutlined />,
      content: (
        <Card>
          <Form.Item
            name="task_name"
            label="任务名称"
            rules={[{ required: true, message: '请输入任务名称' }]}
          >
            <Input 
              placeholder="任务名称将根据模型和数据集自动生成，可手动修改" 
            />
          </Form.Item>

          <Form.Item
            name="eval_backend"
            label="评测后端"
            initialValue="Native"
          >
            <Select>
              <Option value="Native">Native (默认)</Option>
              <Option value="OpenCompass">OpenCompass</Option>
              <Option value="VLMEvalKit">VLMEvalKit</Option>
              <Option value="RAGEval">RAGEval</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="limit"
            label="样本数限制"
            tooltip="每个数据集的最大样本数，留空表示全部"
          >
            <InputNumber
              style={{ width: '100%' }}
              min={1}
              placeholder="留空表示评测全部样本"
            />
          </Form.Item>

          <Form.Item
            name="generation_config"
            label="生成参数"
            tooltip="JSON格式的生成配置"
          >
            <TextArea
              rows={6}
              placeholder={`{
  "do_sample": true,
  "temperature": 0.7,
  "max_tokens": 512,
  "top_p": 0.95
}`}
            />
          </Form.Item>
        </Card>
      )
    },
    {
      title: '确认并启动',
      icon: <CheckCircleOutlined />,
      content: (
        <Card>
          <div style={{ padding: '20px', background: '#f5f5f5', borderRadius: '4px' }}>
            <h3>任务配置确认</h3>
            <Divider />
            
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div>
                <strong>任务名称:</strong> {form.getFieldValue('task_name') || '未设置'}
              </div>
              <div>
                <strong>模型:</strong> {getModelDisplayName(form.getFieldValue('model_id')) || '未选择'}
              </div>
              <div>
                <strong>数据集:</strong> {selectedBenchmarks.length > 0 
                  ? selectedBenchmarks.join(', ') 
                  : '未选择'}
              </div>
              <div>
                <strong>评测后端:</strong> {form.getFieldValue('eval_backend') || 'Native'}
              </div>
              {form.getFieldValue('limit') && (
                <div>
                  <strong>样本限制:</strong> {form.getFieldValue('limit')}
                </div>
              )}
              
              {/* 时间预估显示 */}
              {timeEstimate && (
                <div style={{ marginTop: '16px' }}>
                  <Card 
                    size="small" 
                    title={
                      <Space>
                        <ClockCircleOutlined />
                        <span>评测时间预估</span>
                      </Space>
                    }
                    style={{ backgroundColor: '#f9f9f9' }}
                  >
                    <pre style={{ 
                      whiteSpace: 'pre-wrap', 
                      margin: 0, 
                      fontSize: '12px',
                      fontFamily: 'monospace'
                    }}>
                      {timeEstimate}
                    </pre>
                    
                    {timeWarning.isLong && (
                      <Alert
                        message={timeWarning.warning}
                        description={
                          <ul style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
                            {timeWarning.suggestions.map((suggestion, index) => (
                              <li key={index}>{suggestion}</li>
                            ))}
                          </ul>
                        }
                        type="warning"
                        showIcon
                        style={{ marginTop: '12px' }}
                      />
                    )}
                  </Card>
                </div>
              )}
            </Space>
          </div>

          <div style={{ marginTop: 20, color: '#666' }}>
            <p>⚠️ 提示:</p>
            <ul>
              <li>评测任务将在后台异步执行</li>
              <li>您可以在任务监控页面查看实时进度</li>
              <li>评测完成后会自动生成报告</li>
            </ul>
          </div>
        </Card>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card title="创建评测任务">
        <Steps current={current} style={{ marginBottom: 24 }}>
          {steps.map((item) => (
            <Step key={item.title} title={item.title} icon={item.icon} />
          ))}
        </Steps>

        <Form form={form} layout="vertical">
          <div style={{ minHeight: '400px' }}>
            {steps[current].content}
          </div>

          <Divider />

          <div style={{ textAlign: 'right' }}>
            <Space>
              {current > 0 && (
                <Button onClick={handlePrev}>
                  上一步
                </Button>
              )}
              {current < steps.length - 1 && (
                <Button type="primary" onClick={handleNext}>
                  下一步
                </Button>
              )}
              {current === steps.length - 1 && (
                <Button
                  type="primary"
                  icon={<RocketOutlined />}
                  loading={loading}
                  onClick={handleSubmit}
                  disabled={selectedBenchmarks.length === 0}
                >
                  立即开始评测
                </Button>
              )}
            </Space>
          </div>
        </Form>
      </Card>
    </div>
  );
};

export default TaskCreatePage;

