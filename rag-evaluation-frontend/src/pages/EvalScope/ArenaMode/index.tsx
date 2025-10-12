import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Typography,
  Row,
  Col,
  Space,
  Avatar,
  Progress,
  Tag,
  Table,
  Modal,
  Form,
  Select,
  Input,
  Switch,
  Statistic,
  Alert,
  Divider,
  Badge,
  Tooltip,
  message,
  Steps
} from 'antd';
import {
  ArrowLeftOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  EyeOutlined,
  StarOutlined,
  CrownOutlined,
  FireOutlined,
  ThunderboltOutlined as SwordOutlined,
  SafetyOutlined,
  AimOutlined,
  BarChartOutlined,
  PlusOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { Option } = Select;
const { TextArea } = Input;
const { Step } = Steps;

interface ArenaModel {
  id: string;
  name: string;
  display_name: string;
  rating: number;
  wins: number;
  losses: number;
  draws: number;
  total_battles: number;
  win_rate: number;
  recent_form: ('W' | 'L' | 'D')[];
  tier: 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Diamond' | 'Master';
  avatar?: string;
}

interface ArenaBattle {
  id: string;
  model_a: ArenaModel;
  model_b: ArenaModel;
  dataset: string;
  status: 'pending' | 'running' | 'completed' | 'cancelled';
  result?: 'model_a_wins' | 'model_b_wins' | 'draw';
  score_a?: number;
  score_b?: number;
  created_at: string;
  completed_at?: string;
  voters?: number;
  description?: string;
}

interface ArenaConfig {
  model_a: string;
  model_b: string;
  datasets: string[];
  battle_mode: 'single' | 'best_of_3' | 'tournament';
  evaluation_type: 'automatic' | 'human_voting' | 'hybrid';
  time_limit?: number;
  custom_prompt?: string;
}

const ArenaMobePage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('leaderboard');
  const [createBattleVisible, setCreateBattleVisible] = useState(false);
  const [battleDetailVisible, setBattleDetailVisible] = useState(false);
  const [selectedBattle, setSelectedBattle] = useState<ArenaBattle | null>(null);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [arenaModels, setArenaModels] = useState<ArenaModel[]>([]);

  // 从后端获取模型列表
  const fetchModels = async () => {
    try {
      setModelsLoading(true);
      
      // 获取正确的token
      const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
      
      if (!token) {
        console.error('用户未登录，无法获取Arena模型列表');
        message.error('请先登录');
        return;
      }
      
      // 优先使用统一模型管理API
      const response = await fetch('/api/v1/unified-models/arena', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const models = data.models || [];
        setArenaModels(models);
        console.log('✅ 加载Arena模型列表:', models.length, '个模型');
        
        if (models.length === 0) {
          message.warning({
            content: '未找到可用模型，请先在【API配置管理】或【大模型管理】中配置模型，然后点击【同步现有模型】',
            duration: 6
          });
        }
      } else {
        // 降级到测试接口
        const testResponse = await fetch('/api/v1/unified-models/test/available', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        if (testResponse.ok) {
          const testData = await testResponse.json();
          // 转换为Arena模型格式
          const arenaModels = testData.models.map(model => ({
            ...model,
            rating: model.quality_rating ? model.quality_rating * 150 : 1500, // 转换为ELO评分
            wins: 0,
            losses: 0, 
            draws: 0,
            total_battles: 0,
            win_rate: 0.5,
            recent_form: ['W', 'L', 'W', 'D', 'L'] as ('W' | 'L' | 'D')[], // 模拟近期表现
            tier: 'Bronze' as 'Bronze' | 'Silver' | 'Gold' | 'Platinum' | 'Diamond' | 'Master' // 默认段位
          }));
          setArenaModels(arenaModels);
          console.log('✅ 使用测试Arena模型列表:', arenaModels.length, '个模型');
          
          if (arenaModels.length === 0) {
            message.warning({
              content: '未找到可用模型，请先在【API配置管理】或【大模型管理】中配置模型',
              duration: 6
            });
          }
        } else {
          console.error('❌ 获取模型列表失败:', response.statusText);
          message.error('获取模型列表失败，请检查网络连接或稍后重试');
        }
      }
    } catch (error) {
      console.error('获取模型列表异常:', error);
      message.error('获取模型列表异常');
    } finally {
      setModelsLoading(false);
    }
  };

  // 组件加载时获取模型列表
  useEffect(() => {
    fetchModels();
  }, []);

  // 只使用从API动态获取的模型，不使用硬编码fallback
  const currentModels = arenaModels;

  // 模拟对战记录（确保模型存在）
  const arenaBattles: ArenaBattle[] = currentModels.length >= 2 ? [
    {
      id: 'battle_1',
      model_a: currentModels[0],
      model_b: currentModels[1],
      dataset: 'MMLU',
      status: 'completed',
      result: 'model_a_wins',
      score_a: 0.847,
      score_b: 0.823,
      created_at: '2025-10-09T10:30:00Z',
      completed_at: '2025-10-09T10:45:00Z',
      voters: 156,
      description: '综合知识理解对决'
    },
    ...(currentModels.length >= 4 ? [{
      id: 'battle_2',
      model_a: currentModels[2],
      model_b: currentModels[3],
      dataset: 'GSM8K',
      status: 'running',
      created_at: '2025-10-09T11:00:00Z',
      description: '数学推理能力对战'
    }] : []),
    ...(currentModels.length >= 5 ? [{
      id: 'battle_3',
      model_a: currentModels[1],
      model_b: currentModels[4],
      dataset: 'HumanEval',
      status: 'pending',
      created_at: '2025-10-09T11:15:00Z',
      description: '代码生成挑战赛'
    }] : [])
  ] : [];

  const getTierColor = (tier: string) => {
    const colorMap: { [key: string]: string } = {
      'Bronze': '#cd7f32',
      'Silver': '#c0c0c0',
      'Gold': '#ffd700',
      'Platinum': '#e5e4e2',
      'Diamond': '#b9f2ff',
      'Master': '#ff6b6b'
    };
    return colorMap[tier] || '#d9d9d9';
  };

  const getTierIcon = (tier: string) => {
    const iconMap: { [key: string]: React.ReactNode } = {
      'Bronze': <SafetyOutlined />,
      'Silver': <StarOutlined />,
      'Gold': <TrophyOutlined />,
      'Platinum': <CrownOutlined />,
      'Diamond': <FireOutlined />,
      'Master': <ThunderboltOutlined />
    };
    return iconMap[tier] || <SafetyOutlined />;
  };

  const getFormIcon = (result: string) => {
    const iconMap: { [key: string]: { icon: React.ReactNode, color: string } } = {
      'W': { icon: '●', color: '#52c41a' },
      'L': { icon: '●', color: '#ff4d4f' },
      'D': { icon: '●', color: '#faad14' }
    };
    return iconMap[result] || { icon: '●', color: '#d9d9d9' };
  };

  const handleCreateBattle = async (values: any) => {
    try {
      setLoading(true);
      
      // 获取选中模型的配置信息
      const modelA = currentModels.find(m => m.id === values.model_a);
      const modelB = currentModels.find(m => m.id === values.model_b);
      
      if (!modelA || !modelB) {
        message.error('选择的模型不存在，请重新选择');
        return;
      }

      // 检查模型配置
      if (modelA.config?.model_type === 'api' && !modelA.config?.api_url) {
        message.error(`模型 ${modelA.display_name} 缺少API配置，请在设置中配置`);
        return;
      }

      const config: ArenaConfig = {
        model_a: values.model_a,
        model_b: values.model_b,
        datasets: values.datasets,
        battle_mode: values.battle_mode || 'single',
        evaluation_type: values.evaluation_type || 'automatic',
        time_limit: values.time_limit,
        custom_prompt: values.custom_prompt
      };

      console.log('创建Arena对战:', config);
      console.log('模型A配置:', modelA.config);
      console.log('模型B配置:', modelB.config);

      // 创建对战任务
      const battleData = {
        task_name: `Arena对战: ${modelA.display_name} vs ${modelB.display_name}`,
        model_id: values.model_a, // 使用模型A作为主模型
        datasets: values.datasets,
        model_args: {},
        dataset_args: {},
        generation_config: {},
        eval_backend: 'evalscope',
        eval_type: modelA.config?.model_type === 'api' ? 'openai_api' : 'llm_ckpt',
        limit: 10, // Arena对战默认限制10个样本
        user_model_config: modelA.config // 传递用户模型配置
      };

      // 调用后端API创建对战
      const response = await fetch('/api/v1/evalscope/tasks/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(battleData)
      });

      if (response.ok) {
        const result = await response.json();
        console.log('Arena对战创建成功:', result);
        message.success('Arena对战创建成功！正在执行评测...');
        
        // 刷新模型列表以更新战绩
        await fetchModels();
      } else {
        const error = await response.text();
        console.error('创建Arena对战失败:', error);
        message.error(`创建对战失败: ${error}`);
      }
      
      setCreateBattleVisible(false);
      form.resetFields();
      
    } catch (error) {
      console.error('创建Arena对战失败:', error);
      message.error('创建对战失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const leaderboardColumns = [
    {
      title: '排名',
      key: 'rank',
      width: 80,
      render: (_: any, __: any, index: number) => (
        <Space>
          {index === 0 && <CrownOutlined style={{ color: '#ffd700' }} />}
          <Text strong style={{ color: index < 3 ? '#1890ff' : undefined }}>
            #{index + 1}
          </Text>
        </Space>
      )
    },
    {
      title: '模型',
      key: 'model',
      render: (record: ArenaModel) => (
        <Space>
          <Avatar 
            size="large"
            style={{ backgroundColor: getTierColor(record.tier || 'Bronze') }}
          >
            {(record.name || record.display_name || 'M').charAt(0)}
          </Avatar>
          <div>
            <Text strong>{record.display_name || record.name || '未知模型'}</Text>
            <br />
            <Tag color={getTierColor(record.tier || 'Bronze')} icon={getTierIcon(record.tier || 'Bronze')}>
              {record.tier || 'Bronze'}
            </Tag>
          </div>
        </Space>
      )
    },
    {
      title: 'Rating',
      dataIndex: 'rating',
      key: 'rating',
      render: (rating: number) => (
        <Text strong style={{ fontSize: 16, color: '#1890ff' }}>
          {rating || 1500}
        </Text>
      )
    },
    {
      title: '战绩',
      key: 'record',
      render: (record: ArenaModel) => (
        <Space direction="vertical" size="small">
          <Text>
            {record.wins || 0}胜 {record.losses || 0}负 {record.draws || 0}平
          </Text>
          <Text type="secondary">
            胜率: {(record.win_rate || 0).toFixed(1)}%
          </Text>
        </Space>
      )
    },
    {
      title: '近期表现',
      key: 'recent_form',
      render: (record: ArenaModel) => (
        <Space>
          {(record.recent_form || []).map((result, index) => {
            const { icon, color } = getFormIcon(result);
            return (
              <Tooltip key={index} title={result === 'W' ? '胜' : result === 'L' ? '负' : '平'}>
                <span style={{ color, fontSize: 12 }}>{icon}</span>
              </Tooltip>
            );
          })}
          {(!record.recent_form || record.recent_form.length === 0) && (
            <Text type="secondary">暂无数据</Text>
          )}
        </Space>
      )
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: ArenaModel) => (
        <Space>
          <Button 
            size="small"
            icon={<SwordOutlined />}
            onClick={() => {
              form.setFieldsValue({ model_a: record.id });
              setCreateBattleVisible(true);
            }}
          >
            挑战
          </Button>
          <Button size="small" icon={<EyeOutlined />}>
            详情
          </Button>
        </Space>
      )
    }
  ];

  const battleColumns = [
    {
      title: '对战',
      key: 'battle',
      render: (record: ArenaBattle) => (
        <Space direction="vertical" size="small">
          <Space>
            <Avatar size="small">{(record.model_a?.name || record.model_a?.display_name || 'A').charAt(0)}</Avatar>
            <Text>{record.model_a?.display_name || record.model_a?.name || 'Model A'}</Text>
            <Text type="secondary">vs</Text>
            <Avatar size="small">{(record.model_b?.name || record.model_b?.display_name || 'B').charAt(0)}</Avatar>
            <Text>{record.model_b?.display_name || record.model_b?.name || 'Model B'}</Text>
          </Space>
          <Tag color="blue">{record.dataset}</Tag>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const statusMap: { [key: string]: { color: string, text: string } } = {
          pending: { color: 'default', text: '等待中' },
          running: { color: 'blue', text: '进行中' },
          completed: { color: 'green', text: '已完成' },
          cancelled: { color: 'red', text: '已取消' }
        };
        const { color, text } = statusMap[status] || { color: 'default', text: status };
        return <Tag color={color}>{text}</Tag>;
      }
    },
    {
      title: '结果',
      key: 'result',
      render: (record: ArenaBattle) => {
        if (record.status !== 'completed' || !record.result) {
          return <Text type="secondary">-</Text>;
        }
        
        const winner = record.result === 'model_a_wins' ? record.model_a : 
                      record.result === 'model_b_wins' ? record.model_b : null;
        
        if (!winner) {
          return <Tag color="orange">平局</Tag>;
        }
        
        return (
          <Space direction="vertical" size="small">
            <Space>
              <TrophyOutlined style={{ color: '#ffd700' }} />
              <Text strong>{winner?.display_name || 'Winner'}</Text>
            </Space>
            {record.score_a !== undefined && record.score_b !== undefined && (
              <Text type="secondary">
                {record.score_a.toFixed(3)} vs {record.score_b.toFixed(3)}
              </Text>
            )}
          </Space>
        );
      }
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
      render: (record: ArenaBattle) => (
        <Space>
          <Button 
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setSelectedBattle(record);
              setBattleDetailVisible(true);
            }}
          >
            详情
          </Button>
          {record.status === 'pending' && (
            <Button 
              size="small"
              icon={<PlayCircleOutlined />}
              type="primary"
            >
              开始
            </Button>
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
              <SwordOutlined /> Arena对战模式
            </Title>
            <Text type="secondary">模型PK竞技场</Text>
          </Space>
        </Col>
        <Col>
          <Space>
            <Button 
              icon={<ThunderboltOutlined />}
              onClick={fetchModels}
              loading={modelsLoading}
            >
              刷新模型
            </Button>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setCreateBattleVisible(true)}
            >
              创建对战
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="活跃模型"
              value={currentModels.length}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总对战数"
              value={arenaBattles.length}
              prefix={<SwordOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="进行中"
              value={arenaBattles.filter(b => b.status === 'running').length}
              prefix={<PlayCircleOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="今日投票"
              value={1247}
              prefix={<StarOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 排行榜 */}
      <Card 
        title={
          <Space>
            <TrophyOutlined />
            <Text strong>Arena排行榜</Text>
          </Space>
        }
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={currentModels.sort((a, b) => (b.rating || 1500) - (a.rating || 1500))}
          columns={leaderboardColumns}
          rowKey="id"
          pagination={false}
          loading={modelsLoading}
        />
      </Card>

      {/* 对战记录 */}
      <Card 
        title={
          <Space>
            <BarChartOutlined />
            <Text strong>对战记录</Text>
          </Space>
        }
      >
        <Table
          dataSource={arenaBattles}
          columns={battleColumns}
          rowKey="id"
        />
      </Card>

      {/* 创建对战Modal */}
      <Modal
        title="创建Arena对战"
        open={createBattleVisible}
        onCancel={() => setCreateBattleVisible(false)}
        onOk={() => form.submit()}
        okText="创建对战"
        cancelText="取消"
        width={600}
        confirmLoading={loading}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateBattle}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="model_a"
                label="挑战者A"
                rules={[{ required: true, message: '请选择模型A' }]}
              >
                <Select placeholder="选择模型A" showSearch loading={modelsLoading}>
                  {currentModels.map(model => (
                    <Option key={model.id} value={model.id}>
                      <Space>
                        <Avatar size="small">{(model.name || model.display_name || 'M').charAt(0)}</Avatar>
                        {model.display_name || model.name || '未知模型'}
                        <Text type="secondary">({model.rating || 1500})</Text>
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model_b"
                label="挑战者B"
                rules={[{ required: true, message: '请选择模型B' }]}
              >
                <Select placeholder="选择模型B" showSearch loading={modelsLoading}>
                  {currentModels.map(model => (
                    <Option key={model.id} value={model.id}>
                      <Space>
                        <Avatar size="small">{(model.name || model.display_name || 'M').charAt(0)}</Avatar>
                        {model.display_name || model.name || '未知模型'}
                        <Text type="secondary">({model.rating || 1500})</Text>
                      </Space>
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="datasets"
            label="对战数据集"
            rules={[{ required: true, message: '请选择数据集' }]}
          >
            <Select mode="multiple" placeholder="选择对战使用的数据集">
              <Option value="mmlu">MMLU</Option>
              <Option value="gsm8k">GSM8K</Option>
              <Option value="humaneval">HumanEval</Option>
              <Option value="hellaswag">HellaSwag</Option>
              <Option value="arc">ARC</Option>
              <Option value="ceval">C-Eval</Option>
            </Select>
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="battle_mode"
                label="对战模式"
                initialValue="single"
              >
                <Select>
                  <Option value="single">单场对决</Option>
                  <Option value="best_of_3">三局两胜</Option>
                  <Option value="tournament">锦标赛</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="evaluation_type"
                label="评判方式"
                initialValue="automatic"
              >
                <Select>
                  <Option value="automatic">自动评判</Option>
                  <Option value="human_voting">人工投票</Option>
                  <Option value="hybrid">混合模式</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="custom_prompt"
            label="自定义提示词"
            tooltip="可选：为这场对战设定特殊的评测提示词"
          >
            <TextArea rows={3} placeholder="输入自定义提示词（可选）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 对战详情Modal */}
      <Modal
        title="对战详情"
        open={battleDetailVisible}
        onCancel={() => setBattleDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedBattle && (
          <div>
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={10}>
                <Card size="small">
                  <Space direction="vertical" align="center" style={{ width: '100%' }}>
                    <Avatar size={64}>{(selectedBattle.model_a?.name || selectedBattle.model_a?.display_name || 'A').charAt(0)}</Avatar>
                    <Text strong>{selectedBattle.model_a?.display_name || selectedBattle.model_a?.name || 'Model A'}</Text>
                    <Text type="secondary">Rating: {selectedBattle.model_a?.rating || 1500}</Text>
                    {selectedBattle.score_a !== undefined && (
                      <Statistic 
                        title="得分" 
                        value={selectedBattle.score_a} 
                        precision={3}
                      />
                    )}
                  </Space>
                </Card>
              </Col>
              <Col span={4} style={{ textAlign: 'center', paddingTop: 40 }}>
                <Text strong style={{ fontSize: 18 }}>VS</Text>
              </Col>
              <Col span={10}>
                <Card size="small">
                  <Space direction="vertical" align="center" style={{ width: '100%' }}>
                    <Avatar size={64}>{(selectedBattle.model_b?.name || selectedBattle.model_b?.display_name || 'B').charAt(0)}</Avatar>
                    <Text strong>{selectedBattle.model_b?.display_name || selectedBattle.model_b?.name || 'Model B'}</Text>
                    <Text type="secondary">Rating: {selectedBattle.model_b?.rating || 1500}</Text>
                    {selectedBattle.score_b !== undefined && (
                      <Statistic 
                        title="得分" 
                        value={selectedBattle.score_b} 
                        precision={3}
                      />
                    )}
                  </Space>
                </Card>
              </Col>
            </Row>

            <Card title="对战信息" size="small">
              <Row gutter={16}>
                <Col span={8}>
                  <Text type="secondary">数据集:</Text>
                  <br />
                  <Tag color="blue">{selectedBattle.dataset}</Tag>
                </Col>
                <Col span={8}>
                  <Text type="secondary">状态:</Text>
                  <br />
                  <Tag color={selectedBattle.status === 'completed' ? 'green' : 'blue'}>
                    {selectedBattle.status}
                  </Tag>
                </Col>
                <Col span={8}>
                  <Text type="secondary">投票数:</Text>
                  <br />
                  <Text>{selectedBattle.voters || 0}</Text>
                </Col>
              </Row>
            </Card>

            {selectedBattle.result && (
              <Alert
                message={
                  selectedBattle.result === 'draw' ? 
                    '对战结果：平局' :
                    `对战结果：${
                      selectedBattle.result === 'model_a_wins' ? 
                        (selectedBattle.model_a?.display_name || 'Model A') :
                        (selectedBattle.model_b?.display_name || 'Model B')
                    } 获胜`
                }
                type={selectedBattle.result === 'draw' ? 'info' : 'success'}
                style={{ marginTop: 16 }}
              />
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ArenaMobePage;
