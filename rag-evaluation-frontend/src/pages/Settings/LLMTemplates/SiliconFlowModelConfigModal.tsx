import React, { useEffect } from 'react';
import { Modal, Form, Input, Button, message } from 'antd';
import JsonEditorField from '../../../components/JsonEditorField';
import { labelWithTip } from '../utils';
import { testLLMConnectivity } from '@services/llmProxyService';

// 移除硬编码API地址，由用户配置

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
      message.loading('正在测试模型连通性...', 0);
      
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
      
      const response = await testLLMConnectivity({
        baseUrl: values.baseUrl,
        apiKey: values.apiKey,
        modelName: values.modelName,
        additionalParams,
      });
      
      message.destroy();
      message.success('连接成功！收到响应: ' + (response ? response.substring(0, 20) + '...' : '无内容'));
      
      onSave({
        ...values,
        additionalParams
      });
    } catch (err: any) {
      message.destroy();
      message.error('连接失败: ' + (err.message || '未知错误'));
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
      additionalParams
    });
  };
  return (
    <Modal
      open={open}
      title="硅基流动大模型配置"
      onCancel={onCancel}
      onOk={handleOk}
      destroyOnClose
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
          name="baseUrl"
          label={labelWithTip('BASE_URL', '硅基流动API的基础URL')}
          rules={[{ required: true, message: '请输入BASE_URL' }]}
        >
          <Input placeholder="https://api.siliconflow.cn/v1" />
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
          normalize={(value) => {
            // 确保值始终是字符串
            if (typeof value === 'object' && value !== null) {
              return JSON.stringify(value, null, 2);
            }
            return value || '';
          }}
        >
          <JsonEditorField placeholder='{"temperature": 0.7, "max_tokens": 2048}'/>
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default SiliconFlowModelConfigModal; 