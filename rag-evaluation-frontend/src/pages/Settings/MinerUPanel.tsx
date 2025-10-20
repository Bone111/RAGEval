import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Typography, Alert, Space, Divider } from 'antd';
import { FileTextOutlined, InfoCircleOutlined, SaveOutlined, CopyOutlined } from '@ant-design/icons';
import { ConfigManager } from '../../utils/configManager';
import { mineruService, MinerUDefaultConfig } from '../../services/mineruService';

const { Title, Text } = Typography;

const MinerUPanel: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [defaultConfig, setDefaultConfig] = useState<MinerUDefaultConfig | null>(null);
  const configManager = ConfigManager.getInstance();

  // 加载配置
  useEffect(() => {
    loadConfig();
    loadDefaultConfig();
  }, []);

  // 监听配置变化事件
  useEffect(() => {
    const handleConfigChange = () => {
      loadConfig();
    };

    window.addEventListener('configChanged', handleConfigChange);
    
    return () => {
      window.removeEventListener('configChanged', handleConfigChange);
    };
  }, []);

  const loadConfig = async () => {
    try {
      const configs = await configManager.getAllConfigs('mineru');
      if (configs.length > 0) {
        // 只显示后端返回的配置，不显示缓存的密钥
        const config = configs[0] as any;
        form.setFieldsValue({
          name: config.name,
          baseUrl: config.baseUrl,
          apiKey: config.apiKey // 直接设置密钥，Input.Password 会自动遮盖
        });
      } else {
        // 没有配置时重置表单
        form.setFieldsValue({
          name: 'MinerU API',
          baseUrl: 'https://mineru.net/api/v4',
          apiKey: ''
        });
      }
    } catch (error) {
      console.error('加载MinerU配置失败:', error);
    }
  };

  const loadDefaultConfig = async () => {
    try {
      console.log('开始获取默认配置...');
      const config = await mineruService.getDefaultConfig();
      console.log('获取到的默认配置:', config);
      console.log('default_api_key:', config.default_api_key);
      console.log('expiry_date:', config.expiry_date);
      
      // 直接设置配置，不管是否为空
      setDefaultConfig(config);
    } catch (error) {
      console.error('加载默认配置失败:', error);
      // 出错时设置一个测试配置
      setDefaultConfig({
        default_api_key: '暂无秘钥',
        expiry_date: '----'
      });
    }
  };

  const handleCopyKey = async (key: string) => {
    try {
      await navigator.clipboard.writeText(key);
      message.success('密钥已复制到剪贴板');
    } catch (error) {
      message.error('复制失败');
    }
  };

  const handleSave = async (values: any) => {
    setLoading(true);
    try {
      // 确保使用固定的配置名称
      const configData = {
        ...values,
        name: 'MinerU API'  // 强制使用固定名称
      };
      
      // 如果API密钥不为空，先验证密钥有效性
      if (values.apiKey && values.apiKey.trim() !== '') {
        message.loading('正在验证API密钥...', 0);
        
        try {
          const validationResult = await mineruService.validateApiKey(values.apiKey.trim());
          
          if (!validationResult.isValid) {
            message.destroy();
            message.error(`API密钥验证失败: ${validationResult.error}`);
            return;
          }
          
          message.destroy();
          
          // 验证成功，不显示配额信息
          message.success('API密钥验证成功！');
        } catch (validationError) {
          message.destroy();
          console.error('验证API密钥失败:', validationError);
          message.error('验证API密钥失败，请检查网络连接');
          return;
        }
      }
      
      // 保存配置
      await configManager.createConfig(configData, 'mineru');
      
      // 根据API密钥是否为空显示不同的成功消息
      if (!values.apiKey || values.apiKey.trim() === '') {
        message.success('MinerU API密钥已清空');
      } else {
        message.success('MinerU API密钥配置已保存');
      }
      
      // 触发配置变化事件
      window.dispatchEvent(new CustomEvent('configChanged'));
      
      // 重新加载配置，确保界面显示后端状态
      await loadConfig();
    } catch (error) {
      console.error('保存MinerU配置失败:', error);
      message.error('保存配置失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ width: '100%', maxWidth: 600 }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0, marginBottom: 8 }}>
          <FileTextOutlined style={{ marginRight: 8 }} />
          MinerU 文档解析配置
        </Title>
        <Text type="secondary">
          配置 MinerU API 密钥，用于文档解析功能。密钥将安全存储在服务端。
        </Text>
      </div>

      <Alert
        message="配置说明"
        description={
          <div>
            <div>• MinerU 是一个强大的文档解析工具，支持 PDF、Word、PPT 等多种格式</div>
            <div>• 配置密钥后，系统将优先使用 MinerU 进行文档解析</div>
            <div>• 密钥信息仅存储在服务端，确保安全性</div>
            <div>• 如未配置密钥，系统将使用本地解析功能</div>
          </div>
        }
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      {console.log('渲染时 defaultConfig:', defaultConfig)}
      <Card title="免费秘钥" style={{ marginBottom: 24 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>可用密钥：</Text>
            <Input.Group compact style={{ marginTop: 8 }}>
              <Input
                value={defaultConfig?.default_api_key || '暂无配置'}
                readOnly
                style={{ width: 'calc(100% - 80px)' }}
              />
              <Button 
                type="primary" 
                icon={<CopyOutlined />}
                onClick={() => handleCopyKey(defaultConfig?.default_api_key || '')}
                disabled={!defaultConfig?.default_api_key}
              >
                复制
              </Button>
            </Input.Group>
          </div>
          <div>
            <Text strong>过期时间：</Text>
            <Text style={{ marginLeft: 8 }}>{defaultConfig?.expiry_date || '暂无配置'}</Text>
          </div>
        </Space>
      </Card>

      <Card>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
          initialValues={{
            name: 'MinerU API',
            apiKey: '',
            baseUrl: 'https://mineru.net/api/v4'
          }}
        >
          <Form.Item
            name="name"
            label="配置名称"
          >
            <Input value="MinerU API" disabled />
          </Form.Item>

          <Form.Item
            name="baseUrl"
            label="API 基础地址"
            rules={[{ required: true, message: '请输入API基础地址' }]}
          >
            <Input placeholder="https://mineru.net/api/v4" />
          </Form.Item>

          <Form.Item
            name="apiKey"
            label="API 密钥"
            extra="请输入您的 MinerU API 密钥，留空则清空配置"
          >
            <Input.Password placeholder="请输入您的 MinerU API 密钥" />
          </Form.Item>

          <Divider />

          <Form.Item>
            <Space>
              <Button 
                type="primary" 
                htmlType="submit" 
                loading={loading}
                icon={<SaveOutlined />}
              >
                保存配置
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>

      <Alert
        message="获取 API 密钥"
        description={
          <div>
            <div>1. 访问 <a href="https://mineru.net" target="_blank" rel="noopener noreferrer">MinerU 官网</a></div>
            <div>2. 注册账号并登录</div>
            <div>3. 在个人中心获取 API 密钥</div>
            <div>4. 将密钥粘贴到上方输入框中</div>
          </div>
        }
        type="warning"
        showIcon
        style={{ marginTop: 24 }}
      />

      <Alert
        message="服务说明"
        description={
          <div>
            <div>• 前2000页享受高速通道优先解析</div>
            <div>• 超出额度后仍可继续解析</div>
            <div>• 超额任务按提交时间排队处理</div>
            <div>• 单日0点自动重置额度</div>
          </div>
        }
        type="info"
        showIcon
        style={{ marginTop: 16 }}
      />
    </div>
  );
};

export default MinerUPanel;
