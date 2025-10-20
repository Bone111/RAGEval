import React, { useState, useEffect } from 'react';
import { Form, Input, Button, Card, Typography, message, Row, Col } from 'antd';
import { LockOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import './ResetPassword.css';
import { authService } from '../../services/auth.service';

const { Title, Paragraph } = Typography;

const ResetPassword: React.FC = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const tokenFromUrl = searchParams.get('token');
    const emailFromUrl = searchParams.get('email');
    if (!tokenFromUrl || !emailFromUrl) {
      messageApi.error('无效的重置链接');
      navigate('/login');
      return;
    }
    setToken(tokenFromUrl);
    setEmail(emailFromUrl);
  }, [searchParams, navigate, messageApi]);

  const onFinish = async (values: any) => {
    if (!token || !email) {
      messageApi.error('无效的重置令牌或邮箱');
      return;
    }

    setLoading(true);
    try {
      const response = await authService.resetPassword(token, email, values.new_password);
      messageApi.success(response.message);
      
      // 3秒后跳转到登录页
      setTimeout(() => {
        navigate('/login');
      }, 3000);
      
    } catch (error) {
      console.error('重置密码失败:', error);
      // 错误消息已在authService中处理
    } finally {
      setLoading(false);
    }
  };

  const goBack = () => {
    navigate('/login');
  };

  if (!token || !email) {
    return null; // 等待token和email加载
  }

  return (
    <div className="reset-password-container">
      {contextHolder}
      <div className="reset-password-page-wrapper">
        <div className="reset-password-banner">
          <div className="banner-content">
            <Title level={1} style={{ color: '#fff', marginBottom: 20 }}>RAG评测系统</Title>
            <Paragraph style={{ color: 'rgba(255, 255, 255, 0.8)', fontSize: 16 }}>
              设置您的新密码
            </Paragraph>
          </div>
        </div>
        
        <div className="reset-password-form-container">
          <Card className="reset-password-card" bordered={false}>
            <div className="text-center mb-6">
              <Button 
                type="text" 
                icon={<ArrowLeftOutlined />} 
                onClick={goBack}
                className="back-button"
              >
                返回登录
              </Button>
              <Title level={3} className="text-primary mt-4">重置密码</Title>
              <Paragraph type="secondary">
                请输入您的新密码
              </Paragraph>
            </div>
            
            <Form
              name="reset_password_form"
              onFinish={onFinish}
              layout="vertical"
              size="large"
            >
              <Form.Item
                name="new_password"
                rules={[
                  { required: true, message: '请输入新密码' },
                  { min: 8, message: '密码至少8个字符' }
                ]}
              >
                <Input.Password 
                  prefix={<LockOutlined />} 
                  placeholder="请输入新密码" 
                />
              </Form.Item>
              
              <Form.Item
                name="confirm_password"
                dependencies={['new_password']}
                rules={[
                  { required: true, message: '请确认新密码' },
                  ({ getFieldValue }) => ({
                    validator(_, value) {
                      if (!value || getFieldValue('new_password') === value) {
                        return Promise.resolve();
                      }
                      return Promise.reject(new Error('两次输入的密码不一致'));
                    },
                  }),
                ]}
              >
                <Input.Password 
                  prefix={<LockOutlined />} 
                  placeholder="请再次输入新密码" 
                />
              </Form.Item>
              
              <Form.Item>
                <Button 
                  type="primary" 
                  htmlType="submit" 
                  block 
                  loading={loading}
                  size="large"
                >
                  重置密码
                </Button>
              </Form.Item>
            </Form>
            
            <div className="text-center mt-6">
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                密码重置成功后，请使用新密码登录
              </Paragraph>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
