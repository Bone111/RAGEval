import React, { useState, useEffect } from 'react';
import { Card, Button, Modal, Form, Input, Select, Space, message, Popconfirm, Divider, Typography, Row, Col, Tooltip, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, SettingOutlined, InfoCircleOutlined, QuestionCircleOutlined, DownOutlined, RightOutlined, ClearOutlined, CopyOutlined } from '@ant-design/icons';
import { RAG_TEMPLATES } from './RAGTemplates';
import DifyChatflow from './RAGTemplates/Dify-CHATFLOW';
import DifyFlow from './RAGTemplates/Dify-FLOW';
import CustomRAG from './RAGTemplates/CustomRAG';
import RAGFlowChat from './RAGTemplates/RAGFlowChat';
import { labelWithTip } from './utils';
import OpenAIModelConfigModal from './LLMTemplates/OpenAIModelConfigModal';
import SiliconFlowModelConfigModal from './LLMTemplates/SiliconFlowModelConfigModal';
import { ConfigManager } from '../../utils/configManager';
import ConfigStorageStatus from '../../components/ConfigStorageStatus';

const { Title } = Typography;

// 支持多种大模型配置类型
const MODEL_TEMPLATES = [
  {
    key: 'openai',
    name: '通用大模型',
    desc: 'OpenAI API接口规范',
    logo: '/llm_logo/openai_logo.png',
    defaultConfig: {
      name: '',
      baseUrl: 'https://api.openai.com/v1',
      apiKey: '',
      modelName: 'gpt-4',
      additionalParams: `{
  "temperature": 0.1,
  "max_tokens": 2048
}`,
    }
  },
  {
    key: 'siliconflow',
    name: '硅基流动',
    desc: '硅基流动大模型API',
    logo: '/llm_logo/siliconflow_logo.png',
    defaultConfig: {
      name: '硅基流动',
      baseUrl: 'https://api.siliconflow.cn/v1',
      apiKey: '',
      modelName: 'Qwen/QwQ-32B',
      additionalParams: `{
  "temperature": 0.7,
  "max_tokens": 2048
}`,
    }
  },
  {
    key: 'ollama',
    name: 'Ollama本地模型',
    desc: '本地部署的Ollama模型服务',
    logo: '/llm_logo/ollama_logo.png',
    defaultConfig: {
      name: 'Ollama本地模型',
      baseUrl: 'http://localhost:11434/v1',
      apiKey: 'ollama', // Ollama通常不需要API Key，但保持字段一致
      modelName: 'llama3.2',
      additionalParams: `{
  "temperature": 0.7,
  "max_tokens": 2048,
  "stream": false
}`,
    }
  },
  {
    key: 'local_api',
    name: '本地API服务',
    desc: '本地部署的模型API服务',
    logo: '/llm_logo/local_api_logo.png',
    defaultConfig: {
      name: '本地API服务',
      baseUrl: 'http://localhost:8000/v1',
      apiKey: '',
      modelName: 'local-model',
      additionalParams: `{
  "temperature": 0.7,
  "max_tokens": 2048
}`,
    }
  }
];


const cardStyle: React.CSSProperties = {
  textAlign: 'center',
  minHeight: 200,
  borderRadius: 10,
  boxShadow: '0 2px 8px #f0f1f2',
  transition: 'box-shadow 0.2s',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 16,
  marginRight: 20,
};
const logoStyle: React.CSSProperties = {
  width: 32,
  height: 32,
  marginBottom: 8,
  objectFit: 'contain',
  borderRadius: 6,
  background: '#f5f6fa',
  boxShadow: '0 1px 4px #e0e0e0',
};

// 1. 新增：定义RagConfigModal组件，专门处理rag弹窗内容和保存
const RagConfigModal = ({
  open,
  onCancel,
  onSave,
  template,
  editValue
}: {
  open: boolean;
  onCancel: () => void;
  onSave: (values: any) => void;
  template: any;
  editValue: any;
}) => {
  if (!template) return null;
  if (template.key === 'dify_chatflow') {
    return <DifyChatflow open={open} onCancel={onCancel} onSave={onSave} initialValues={editValue} />;
  }
  if (template.key === 'dify_flow') {
    return <DifyFlow open={open} onCancel={onCancel} onSave={onSave} initialValues={editValue} />;
  }
  if (template.key === 'custom') {
    return <CustomRAG open={open} onCancel={onCancel} onSave={onSave} initialValues={editValue} />;
  }
  if (template.key === 'ragflow_chat') {
    return <RAGFlowChat open={open} onCancel={onCancel} onSave={onSave} initialValues={editValue} />;
  }
  // 其他RAG模板可在此扩展
  return null;
};

const ProviderPanel: React.FC = () => {
  const configManager = ConfigManager.getInstance();
  const [modelConfigs, setModelConfigs] = useState<any[]>([]);
  const [ragConfigs, setRagConfigs] = useState<any[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState<'model' | 'rag'>('model');
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [form] = Form.useForm();
  const [currentTemplate, setCurrentTemplate] = useState<any>(null);
  const [currentEditValue, setCurrentEditValue] = useState<any>({});
  const [currentCopyValue, setCurrentCopyValue] = useState<any>({}); // 存储复制的配置值
  const [marketOpen, setMarketOpen] = useState(true); // 控制配置市场展开/收起

  // 加载配置函数
  const loadConfigs = async () => {
    try {
      const models = await configManager.getAllConfigs('model');
      const rags = await configManager.getAllConfigs('rag');
      setModelConfigs(models);
      setRagConfigs(rags);
    } catch (error) {
      console.error('加载配置失败:', error);
      message.error('加载配置失败');
    }
  };

  // 加载配置
  useEffect(() => {
    loadConfigs();
  }, []);

  // 添加模型
  const handleAddModel = (tplKey = 'openai') => {
    setModalType('model');
    const tpl = MODEL_TEMPLATES.find(t => t.key === tplKey) || MODEL_TEMPLATES[0];
    setCurrentTemplate(tpl);
    setEditIndex(null);
    form.setFieldsValue({ ...tpl.defaultConfig });
    setModalOpen(true);
  };

  // 编辑模型配置
  const handleEditModel = (idx: number) => {
    if (idx < 0 || idx >= modelConfigs.length) {
      message.error('配置索引无效，请刷新页面重试');
      return;
    }
    
    setModalType('model');
    const model = modelConfigs[idx];
    const template = MODEL_TEMPLATES.find(t => t.key === model.type) || MODEL_TEMPLATES[0];
    setCurrentTemplate(template);
    setEditIndex(idx);
    form.setFieldsValue(model);
    setModalOpen(true);
  };

  // 保存模型配置
  const handleModelSave = async (values: any) => {
    try {
      if (editIndex !== null) {
        const updatedConfig = await configManager.updateConfig(
          modelConfigs[editIndex].id,
          { ...values, type: currentTemplate?.key },
          'model'
        );
        if (updatedConfig) {
          setModelConfigs(prev => prev.map((config, i) => i === editIndex ? updatedConfig : config));
        }
      } else {
        const newConfig = await configManager.createConfig({
          ...values,
          type: currentTemplate?.key,
        }, 'model');
        setModelConfigs(prev => [...prev, newConfig]);
      }
      setEditIndex(null);
      setModalOpen(false);
      setCurrentCopyValue({}); // 清空复制值
      message.success('模型配置已保存');
    } catch (error) {
      console.error('保存配置失败:', error);
      message.error('保存配置失败');
    }
  };

  // 删除模型配置
  const handleDeleteModel = async (configId: string) => {
    try {
      if (await configManager.deleteConfig(configId, 'model')) {
        setModelConfigs(prev => prev.filter(c => c.id !== configId));
        message.success('已删除模型配置');
      }
    } catch (error) {
      console.error('删除配置失败:', error);
      message.error('删除配置失败');
    }
  };

  // 复制模型配置
  const handleCopyModel = (idx: number) => {
    if (idx < 0 || idx >= modelConfigs.length) {
      message.error('配置索引无效，请刷新页面重试');
      return;
    }
    
    const originalConfig = modelConfigs[idx];
    const template = MODEL_TEMPLATES.find(t => t.key === originalConfig.type) || MODEL_TEMPLATES[0];
    
    // 创建复制的配置，名称添加_copy后缀
    const copiedConfig = {
      ...originalConfig,
      name: `${originalConfig.name}_copy`,
      id: undefined, // 清除ID，让系统生成新的
    };
    
    setModalType('model');
    setCurrentTemplate(template);
    setEditIndex(null); // 设置为null表示新增
    setCurrentCopyValue(copiedConfig); // 存储复制的配置值
    setModalOpen(true);
  };

  // 修改 handleAddRag/handleEditRag 只控制弹窗开关和传递模板/初始值
  const handleAddRag = (template: any) => {
    setModalType('rag');
    setCurrentTemplate(template);
    setEditIndex(null);
    // 针对dify_chatflow和dify_flow设置默认url
    let defaultConfig = template.defaultConfig;
    if (template.key === 'dify_chatflow') {
      defaultConfig = {
        ...defaultConfig,
        name: 'Dify-Chatflow',
        url: 'http://localhost/v1/chat-messages',
      };
    }
    if (template.key === 'dify_flow') {
      defaultConfig = {
        ...defaultConfig,
        name: 'Dify-工作流',
        url: 'http://localhost/v1/workflows/run',
      };
    }
    if (template.key === 'ragflow'){
      defaultConfig = {
        ...defaultConfig,
        name: 'RAGFlow-Chat',
        url: 'http://localhost/v1/workflows/run',
      };
    }
    setCurrentEditValue(defaultConfig);
    setModalOpen(true);
  };
  const handleEditRag = (idx: number) => {
    if (idx < 0 || idx >= ragConfigs.length) {
      message.error('配置索引无效，请刷新页面重试');
      return;
    }
    
    setModalType('rag');
    const rag = ragConfigs[idx];
    const template = RAG_TEMPLATES.find(t => t.key === rag.type) || RAG_TEMPLATES[0];
    setCurrentTemplate(template);
    setEditIndex(idx);
    setCurrentEditValue(rag);
    setModalOpen(true);
  };
  const handleDeleteRag = (idx: number) => {
    const newList = [...ragConfigs];
    newList.splice(idx, 1);
    configManager.deleteConfig(ragConfigs[idx].id, 'rag');
    setRagConfigs(newList);
    message.success('已删除RAG系统配置');
  };

  // 复制RAG系统配置
  const handleCopyRag = (idx: number) => {
    if (idx < 0 || idx >= ragConfigs.length) {
      message.error('配置索引无效，请刷新页面重试');
      return;
    }
    
    const originalConfig = ragConfigs[idx];
    const template = RAG_TEMPLATES.find(t => t.key === originalConfig.type) || RAG_TEMPLATES[0];
    
    // 创建复制的配置，名称添加_copy后缀
    const copiedConfig = {
      ...originalConfig,
      name: `${originalConfig.name}_copy`,
      id: undefined, // 清除ID，让系统生成新的
    };
    
    setModalType('rag');
    setCurrentTemplate(template);
    setEditIndex(null); // 设置为null表示新增
    setCurrentEditValue(copiedConfig);
    setModalOpen(true);
  };

  // 新增rag保存回调
  const handleRagSave = async (values: any) => {
    try {
      let newList = [...ragConfigs];
      if (editIndex !== null) {
        const updatedConfig = await configManager.updateConfig(ragConfigs[editIndex].id, { ...values, type: currentTemplate.key }, 'rag');
        if (updatedConfig) {
          newList[editIndex] = updatedConfig;
        }
      } else {
        const newConfig = await configManager.createConfig({ ...values, type: currentTemplate.key }, 'rag');
        newList.push(newConfig);
      }
      setRagConfigs(newList);
      setModalOpen(false);
      setCurrentCopyValue({}); // 清空复制值
      message.success('RAG系统配置已保存');
    } catch (error) {
      console.error('保存RAG配置失败:', error);
      message.error('保存配置失败');
    }
  };


  return (
    <div style={{ width: '100%', height: '100%', overflow: 'hidden' }}>
      <div style={{ height: '100%', overflowY: 'auto', padding: '0 1px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <Title level={4} style={{ margin: 0, marginRight: 8 }}>模型提供商</Title>
          <Tooltip
          placement="right"
          title={
            <div style={{ maxWidth: 300 }}>
              <div style={{ marginBottom: 8, fontWeight: 500 }}>数据存储说明</div>
              <div style={{ color: '#fff', fontSize: 13, lineHeight: '1.5' }}>
                <div style={{ marginBottom: 4 }}>• 配置优先保存到服务端，支持跨设备同步</div>
                <div style={{ marginBottom: 4 }}>• 服务端不可用时自动降级到本地存储</div>
                <div style={{ marginBottom: 4 }}>• 所有数据仅限当前用户访问</div>
                <div>• 测试请求直接从浏览器发送至API服务</div>
              </div>
            </div>
          }
        >
          <InfoCircleOutlined style={{ color: '#8c8c8c', cursor: 'help' }} />
          </Tooltip>
        </div>
        <Popconfirm
          title="清除所有配置"
          description="确定要清除所有模型和RAG系统配置吗？此操作不可恢复。"
          onConfirm={async () => {
            try {
              await configManager.clearUserConfigs();
              
              // 重置任何可能影响编辑功能的状态
              setModalOpen(false);
              setEditIndex(null);
              setCurrentTemplate(null);
              setCurrentEditValue({});
              
              // 重新加载配置以确保状态同步
              await loadConfigs();
              
              message.success('已清除所有配置');
            } catch (error) {
              console.error('清除配置失败:', error);
              message.error('清除配置失败');
            }
          }}
          okText="确定"
          cancelText="取消"
        >
          <Button icon={<ClearOutlined />} danger>清除所有配置</Button>
        </Popconfirm>
      </div>
      <div style={{ marginBottom: 24, fontSize: 15, color: '#666' }}>
        在此设置模型参数和API KEY，用于【AI生成问答对】和【AI精度评测】功能。
      </div>
      
      {/* 配置存储状态提示 */}
      <ConfigStorageStatus />
      {/* 已添加模型和RAG系统（合并展示） */}
      {/* <Divider orientation="left"></Divider> */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 15, margin: '12px 0 8px 0', color: '#3b3b3b' }}>大模型配置</div>
        {modelConfigs.length === 0 ? <div style={{ color: '#aaa', marginBottom: 16 }}>暂无已添加模型</div> :
          modelConfigs.map((item, idx) => {
            const tpl = MODEL_TEMPLATES.find(t => t.key === item.type) || MODEL_TEMPLATES[0];
            return (
              <Card key={idx} style={{ marginBottom: 10, borderRadius: 10 ,background:"#f6f7f9",border:0}} styles={{ body: { padding: 0,paddingRight:20 } }}>
              <Row align="middle" justify="start" style={{ minHeight: 64 }}>
                <Col flex="64px" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <img src={tpl.logo} alt="logo" style={{ width: 40, height: 40, objectFit: 'contain', borderRadius: 8 }} />
                </Col>
                <Col flex="auto" style={{ padding: '12px 0 12px 12px' }}>
                  <div style={{ fontWeight: 600, fontSize: 18 }}>{item.name}</div>
                  <div style={{ fontSize: 13, color: '#888' }}>{item.modelName}</div>
                </Col>
                <Col>
                  <Space>
                    <Button 
                      icon={<SettingOutlined />} 
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleEditModel(idx);
                      }}
                    >
                      编辑
                    </Button>
                    <Button 
                      icon={<CopyOutlined />} 
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleCopyModel(idx);
                      }}
                    >
                      复制
                    </Button>
                    <Popconfirm 
                      title="确定删除该模型配置？" 
                      onConfirm={(e) => {
                        e?.preventDefault();
                        e?.stopPropagation();
                        handleDeleteModel(item.id);
                      }}
                    >
                      <Button 
                        icon={<DeleteOutlined />} 
                        danger
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                        }}
                      >
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                </Col>
              </Row>
              </Card>
            );
          })}
      </div>
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 600, fontSize: 15, margin: '12px 0 8px 0', color: '#3b3b3b' }}>RAG系统配置</div>
        {ragConfigs.length === 0 ? <div style={{ color: '#aaa', marginBottom: 16 }}>暂无已添加RAG系统</div> :
          ragConfigs.map((item, idx) => {
            // 获取logo和类型名
            const tpl = RAG_TEMPLATES.find(t => t.key === item.type) || RAG_TEMPLATES[0];
            return (
              <Card key={idx} style={{ marginBottom: 10, borderRadius: 10 ,background:"#f6f7f9",border:0}} styles={{ body: { padding: 0 ,paddingRight:20} }}>
                <Row align="middle" justify="start" style={{ minHeight: 64 }}>
                  <Col flex="64px" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <img src={tpl.logo} alt="logo" style={{ width: 40, height: 40, objectFit: 'contain', borderRadius: 8 }} />
                  </Col>
                  <Col flex="auto" style={{ padding: '12px 0 12px 12px' }}>
                    <div style={{ fontWeight: 600, fontSize: 18 }}>{item.name}</div>
                    <div style={{ fontSize: 13, color: '#888' }}>{tpl.name}</div>
                  </Col>
                  <Col>
                    <Space>
                      <Button 
                        icon={<SettingOutlined />} 
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleEditRag(idx);
                        }}
                      >
                        编辑
                      </Button>
                      <Button 
                        icon={<CopyOutlined />} 
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          handleCopyRag(idx);
                        }}
                      >
                        复制
                      </Button>
                      <Popconfirm 
                        title="确定删除该RAG系统配置？" 
                        onConfirm={(e) => {
                          e?.preventDefault();
                          e?.stopPropagation();
                          handleDeleteRag(idx);
                        }}
                      >
                        <Button 
                          icon={<DeleteOutlined />} 
                          danger
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                        >
                          删除
                        </Button>
                      </Popconfirm>
                    </Space>
                  </Col>
                </Row>
              </Card>
            );
          })}
      </div>
      {/* 配置市场（可收起/展开） */}
      <div style={{ marginBottom: 24, overflow: 'hidden' }}>
        <div
          style={{ cursor: 'pointer', fontWeight: 600, fontSize: 18, padding: '10px 0 10px 2px', borderBottom: marketOpen ? '1px solid #f0f0f0' : 'none', display: 'flex', alignItems: 'center' }}
          onClick={() => setMarketOpen(v => !v)}
        >
          {marketOpen ? <DownOutlined style={{ marginRight: 8 }} /> : <RightOutlined style={{ marginRight: 8 }} />}
          配置市场
        </div>
        {marketOpen && (
          <div style={{ padding: '8px 0 0 0', overflow: 'visible' }}>
            <div style={{ fontWeight: 500, fontSize: 15, margin: '0 0 12px 2px', color: '#3b3b3b' }}>模型配置</div>
            <Row gutter={[24, 24]} justify="start" align="top" style={{ marginBottom: 24 }}>
              {MODEL_TEMPLATES.map((tpl, idx) => (
                <Col key={tpl.key} xs={24} sm={12} md={8} lg={8} xl={8} style={{ display: 'flex' }}>
                  <Card hoverable style={{ ...cardStyle, padding: 0, width: '100%', minHeight: 180 }} styles={{ body: { padding: 0, width: '100%' } }}>
                    <div style={{ display: 'flex', padding: 16, alignItems: 'flex-start' }}>
                      <img src={tpl.logo} alt={tpl.name} style={{ width: 40, height: 40, borderRadius: 8, background: '#f5f6fa', boxShadow: '0 1px 4px #e0e0e0' }} />
                      <div style={{ marginLeft: 20 }}>
                        <div style={{ fontWeight: 600, fontSize: 17, lineHeight: '22px' }}>{tpl.name}</div>
                        <div style={{ fontSize: 13, color: '#888', marginTop: 2, textAlign: 'left' }}>{tpl.key}</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 13, color: '#888', minHeight: 18, padding: '0 16px 8px 16px', textAlign: 'left' }}>{tpl.desc}</div>
                    <div style={{ padding: '0 16px 16px 16px', textAlign: 'left' }}>
                      <Button type="link" icon={<PlusOutlined />} onClick={() => handleAddModel(tpl.key)} style={{ marginTop: 6, padding: 0 }}>添加模型</Button>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
            <div style={{ fontWeight: 500, fontSize: 15, margin: '0 0 12px 2px', color: '#3b3b3b' }}>RAG系统配置</div>
            <Row gutter={[24, 24]} justify="start" align="top" style={{ marginBottom: 8 }}>
              {RAG_TEMPLATES.map((tpl, idx) => (
                <Col key={tpl.key} xs={24} sm={12} md={8} lg={8} xl={8} style={{ display: 'flex' }}>
                  <Card hoverable style={{ ...cardStyle, padding: 0, width: '100%', minHeight: 180 }} styles={{ body: { padding: 0, width: '100%' } }}>
                    <div style={{ display: 'flex', padding: 16, alignItems: 'flex-start' }}>
                      <img src={tpl.logo} alt={tpl.name} style={{ width: 40, height: 40, borderRadius: 8, background: '#f5f6fa', boxShadow: '0 1px 4px #e0e0e0' }} />
                      <div style={{ marginLeft: 20 }}>
                        <div style={{ fontWeight: 600, fontSize: 17, lineHeight: '22px' }}>{tpl.name}</div>
                        <div style={{ fontSize: 13, color: '#888', marginTop: 2, textAlign: 'left' }}>{tpl.key}</div>
                      </div>
                    </div>
                    <div style={{ fontSize: 13, color: '#888', minHeight: 18, padding: '0 16px 8px 16px', textAlign: 'left' }}>{tpl.desc}</div>
                    <div style={{ padding: '0 16px 16px 16px', textAlign: 'left' }}>
                      <Button type="link" icon={<PlusOutlined />} onClick={() => handleAddRag(tpl)} style={{ marginTop: 6, padding: 0 }}>添加RAG系统</Button>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </div>
        )}
        </div>
      </div>
      {/* 配置弹窗 */}
      {modalType === 'model' ? (
        ['ollama', 'local_api', 'openai'].includes(currentTemplate?.key) ? (
          <OpenAIModelConfigModal
            open={modalOpen}
            onCancel={() => {
              setModalOpen(false);
              setCurrentCopyValue({}); // 清空复制值
            }}
            onSave={handleModelSave}
            initialValues={editIndex !== null ? modelConfigs[editIndex] : (Object.keys(currentCopyValue).length > 0 ? currentCopyValue : currentTemplate?.defaultConfig)}
            templateKey={currentTemplate?.key}
          />
        ) : currentTemplate?.key === 'siliconflow' ? (
          <SiliconFlowModelConfigModal
            open={modalOpen}
            onCancel={() => {
              setModalOpen(false);
              setCurrentCopyValue({}); // 清空复制值
            }}
            onSave={handleModelSave}
            initialValues={editIndex !== null ? modelConfigs[editIndex] : (Object.keys(currentCopyValue).length > 0 ? currentCopyValue : currentTemplate?.defaultConfig)}
          />
        ) : (
          <OpenAIModelConfigModal
            open={modalOpen}
            onCancel={() => {
              setModalOpen(false);
              setCurrentCopyValue({}); // 清空复制值
            }}
            onSave={handleModelSave}
            initialValues={editIndex !== null ? modelConfigs[editIndex] : (Object.keys(currentCopyValue).length > 0 ? currentCopyValue : currentTemplate?.defaultConfig)}
            templateKey={currentTemplate?.key}
          />
        )
      ) : (
        <RagConfigModal
          open={modalOpen}
          onCancel={() => setModalOpen(false)}
          onSave={handleRagSave}
          template={currentTemplate}
          editValue={currentEditValue}
        />
      )}
    </div>
  );
};

export default ProviderPanel; 