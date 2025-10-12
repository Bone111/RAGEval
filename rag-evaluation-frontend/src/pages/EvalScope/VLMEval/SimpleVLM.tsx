import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Form,
  Input,
  Select,
  Space,
  Typography,
  Row,
  Col,
  Tag,
  Alert,
  message
} from 'antd';
import {
  ArrowLeftOutlined,
  PictureOutlined,
  PlayCircleOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;
const { Option } = Select;

const SimpleVLMPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const vlmModels = [
    { value: 'qwen-vl-chat', label: 'Qwen-VL-Chat' },
    { value: 'llava-v1.5-7b', label: 'LLaVA-1.5-7B' },
    { value: 'custom-api', label: '自定义API模型' }
  ];

  const vlmDatasets = [
    'MMBench_DEV_EN',
    'MME',
    'SEEDBench_IMG',
    'MMVet',
    'MMMU_DEV_VAL',
    'MathVista_MINI',
    'OCRBench',
    'ChartQA_TEST',
    'AI2D_TEST'
  ];

  const handleSubmit = async (values: any) => {
    try {
      setLoading(true);
      console.log('VLM评测任务:', values);
      message.success('VLM评测任务已创建！（演示模式）');
      navigate('/evalscope/tasks');
    } catch (error) {
      console.error('创建任务失败:', error);
      message.error('创建任务失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
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
              <PictureOutlined /> VLM多模态评测
            </Title>
          </Space>
        </Col>
      </Row>

      <Card title="创建VLM评测任务">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            limit: 50,
            temperature: 0.0
          }}
        >
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="task_name"
                label="任务名称"
                rules={[{ required: true, message: '请输入任务名称' }]}
              >
                <Input placeholder="输入VLM评测任务名称" />
              </Form.Item>

              <Form.Item
                name="model_id"
                label="选择模型"
                rules={[{ required: true, message: '请选择VLM模型' }]}
              >
                <Select placeholder="选择多模态模型">
                  {vlmModels.map(model => (
                    <Option key={model.value} value={model.value}>
                      {model.label}
                    </Option>
                  ))}
                </Select>
              </Form.Item>

              <Form.Item
                name="datasets"
                label="选择数据集"
                rules={[{ required: true, message: '请选择数据集' }]}
              >
                <Select mode="multiple" placeholder="选择评测数据集">
                  {vlmDatasets.map(dataset => (
                    <Option key={dataset} value={dataset}>
                      {dataset}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>

            <Col span={12}>
              <Form.Item
                name="limit"
                label="样本限制"
                tooltip="限制每个数据集的样本数量"
              >
                <Input type="number" placeholder="50" />
              </Form.Item>

              <Form.Item
                name="temperature"
                label="生成温度"
                tooltip="控制生成的随机性"
              >
                <Input type="number" placeholder="0.0" />
              </Form.Item>

              <Form.Item
                name="max_tokens"
                label="最大Token数"
              >
                <Input type="number" placeholder="1024" />
              </Form.Item>
            </Col>
          </Row>

          <Alert
            message="VLM多模态评测说明"
            description="VLM评测将测试模型的视觉理解、图像推理、OCR识别等多模态能力"
            type="info"
            style={{ marginBottom: 16 }}
          />

          <Form.Item>
            <Button 
              type="primary" 
              htmlType="submit"
              loading={loading}
              icon={<PlayCircleOutlined />}
              size="large"
            >
              开始VLM评测
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default SimpleVLMPage;


