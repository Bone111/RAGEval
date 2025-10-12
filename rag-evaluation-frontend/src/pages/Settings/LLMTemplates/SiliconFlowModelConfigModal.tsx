import React, { useEffect } from 'react';
import { Modal, Form, Input, Button, message } from 'antd';
import JsonEditorField from '@components/JsonEditorField';
import { labelWithTip } from '../utils';
import { LLMClient, ChatCompletionMessageParam } from './llm-request';

const API_URL = 'https://api.siliconflow.cn/v1';

const SiliconFlowModelConfigModal: React.FC<{
  open: boolean;
  onCancel: () => void;
  onSave: (values: any) => void;
  initialValues: any;
}> = ({ open, onCancel, onSave, initialValues }) => {
  const [form] = Form.useForm();
  const [loading, setLoading] = React.useState(false);

  useEffect(() => {
    if (open) {
      form.resetFields();
      const { baseUrl, ...rest } = initialValues || {};
      // 确保additionalParams是字符串格式
      const processedValues = {
        ...rest,
        additionalParams: typeof rest.additionalParams === 'object' 
          ? JSON.stringify(rest.additionalParams, null, 2)
          : rest.additionalParams
      };
      form.setFieldsValue(processedValues);
    }
  }, [open, initialValues, form]);

  const handleTestAndSave = async () => {
    try {
      const values = await form.validateFields();
      setLoading(true);
      const hide = message.loading('正在测试模型连通性...', 0);
      
      // 安全解析additionalParams
      let additionalParams: any = {};
      if (values.additionalParams) {
        try {
          additionalParams = typeof values.additionalParams === 'string' 
            ? JSON.parse(values.additionalParams) 
            : values.additionalParams;
        } catch {
          additionalParams = {};
        }
      }
      
      // 优先使用后端代理测试（避免CORS问题）
      try {
        const response = await fetch('/api/v1/user-configs/model-configs/test-connection', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('access_token') || sessionStorage.getItem('access_token')}`
          },
          body: JSON.stringify({
            baseUrl: API_URL,
            apiKey: values.apiKey,
            modelName: values.modelName,
            additionalParams
          })
        });
        
        hide();
        
        if (response.ok) {
          const result = await response.json();
          if (result.success) {
            message.success(`✅ 连接成功！模型响应: ${result.response}`);
            onSave({
              ...values,
              baseUrl: API_URL,
              additionalParams
            });
            return;
          } else {
            message.error(`❌ ${result.message}: ${result.error || ''}`);
            return;
          }
        } else {
          const error = await response.json().catch(() => ({ detail: '测试失败' }));
          message.error(`❌ 连接测试失败: ${error.detail || response.statusText}`);
          return;
        }
      } catch (fetchError: any) {
        hide();
        console.warn('后端代理失败，尝试直接连接:', fetchError);
        
        // 后端代理失败，尝试直接连接（仅支持CORS的API可用）
        try {
          const loadingMsg = message.loading('尝试直接连接...', 0);
          const client = new LLMClient({
            baseUrl: API_URL,
            apiKey: values.apiKey,
            modelName: values.modelName,
          });
          const content = await client.chatCompletion({
            userMessage: '你好',
            additionalParams,
          });
          loadingMsg();
          message.success('✅ 连接成功！收到响应: ' + (content ? content.substring(0, 20) + '...' : '无内容'));
          onSave({
            ...values,
            baseUrl: API_URL,
            additionalParams
          });
        } catch (directError: any) {
          message.error(`❌ 连接失败: ${directError.message || '请检查配置或网络'}。提示: 部分API不支持浏览器直接访问，但配置仍可保存使用。`);
        }
      }
    } catch (err: any) {
      message.error(err.message || '表单校验失败');
    } finally {
      setLoading(false);
    }
  };

  const handleOk = async () => {
    const values = await form.validateFields();
    
    // 安全解析additionalParams
    let additionalParams;
    if (values.additionalParams) {
      try {
        additionalParams = typeof values.additionalParams === 'string' 
          ? JSON.parse(values.additionalParams) 
          : values.additionalParams;
      } catch {
        additionalParams = {};
      }
    }
    
    onSave({
      ...values,
      baseUrl: API_URL,
      additionalParams
    });
  };
  return (
    <Modal
      open={open}
      title="硅基流动大模型配置"
      onCancel={onCancel}
      onOk={handleOk}
      destroyOnHidden
      width={480}
      okText="保存"
      footer={[
        <Button key="test" type="primary" loading={loading} onClick={handleTestAndSave}>测试并保存</Button>,
        <Button key="cancel" onClick={onCancel}>取消</Button>,
      ]}
    >
      <Form
        form={form}
        layout="vertical"
      >
        <Form.Item
          name="name"
          label={labelWithTip('配置名称', '自定义本配置的名称，便于区分多个模型账号')}
          rules={[{ required: true, message: '请输入配置名称' }]}
        >
          <Input placeholder="如：硅基流动" />
        </Form.Item>
        <Form.Item
          name="apiKey"
          label={labelWithTip('API_KEY', '硅基流动的API密钥')}
          rules={[{ required: true, message: '请输入API密钥' }]}>
          <Input.Password placeholder="token..." />
        </Form.Item>
        <Form.Item
          name="modelName"
          label={labelWithTip('模型名称', '如 Qwen/QwQ-32B，具体见API文档')}
          rules={[{ required: true, message: '请输入模型名称' }]}>
          <Input placeholder="Qwen/QwQ-32B" />
        </Form.Item>
        <Form.Item
          name="additionalParams"
          label={labelWithTip('高级参数(JSON)', '如temperature、max_tokens等，需为合法JSON格式')}
          rules={[{
            validator: (_, value) => {
              if (!value) return Promise.resolve();
              try { JSON.parse(value); return Promise.resolve(); } catch { return Promise.reject('请输入有效的JSON格式'); }
            }
          }]}
          valuePropName="value"
          getValueFromEvent={v => v}
        >
          <JsonEditorField placeholder='{"temperature": 0.7, "max_tokens": 2048}'/>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default SiliconFlowModelConfigModal; 