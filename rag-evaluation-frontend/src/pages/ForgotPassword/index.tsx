import React, { useState } from 'react';
import { Form, Input, Button, Card, Typography, message, Row, Col } from 'antd';
import { UserOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import './ForgotPassword.css';
import { authService } from '../../services/auth.service';

const { Title, Paragraph } = Typography;

const ForgotPassword: React.FC = () => {
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const onFinish = async (values: any) => {
    setLoading(true);
    try {
      const response = await authService.forgotPassword(values.email);
      
      // 如果邮件发送成功，显示成功消息并跳转
      if (!response.contact_info) {
        messageApi.success(response.message);
        setTimeout(() => {
          navigate('/login');
        }, 3000);
      } else {
        // 如果邮件发送失败，显示警告消息和联系管理员信息
        messageApi.warning({
          content: (
            <div>
              <div>{response.message}</div>
              <div style={{ marginTop: 8, fontSize: 12, color: '#666' }}>
                {response.contact_info}
              </div>
              {response.reset_url && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#1890ff' }}>
                  开发环境重置链接已生成，请查看控制台
                </div>
              )}
            </div>
          ),
          duration: 10,
        });
      }
      
    } catch (error) {
      console.error('发送重置密码邮件失败:', error);
      // 错误消息已在authService中处理
    } finally {
      setLoading(false);
    }
  };

  const goBack = () => {
    navigate('/login');
  };

  return (
    <div className="forgot-password-container">
      {contextHolder}
      <div className="forgot-password-page-wrapper">
        <div className="forgot-password-banner">
          <div className="banner-content">
            <Title level={1} style={{ color: '#fff', marginBottom: 20 }}>RAG评测系统</Title>
            <Paragraph style={{ color: 'rgba(255, 255, 255, 0.8)', fontSize: 16 }}>
              重置您的账户密码
            </Paragraph>
          </div>
        </div>
        
        <div className="forgot-password-form-container">
          <Card className="forgot-password-card" bordered={false}>
            <div className="text-center mb-6">
              <Button 
                type="text" 
                icon={<ArrowLeftOutlined />} 
                onClick={goBack}
                className="back-button"
              >
                返回登录
              </Button>
              <Title level={3} className="text-primary mt-4">忘记密码</Title>
              <Paragraph type="secondary">
                请输入您的邮箱地址，我们将发送重置密码的链接给您
              </Paragraph>
            </div>
            
            <Form
              name="forgot_password_form"
              onFinish={onFinish}
              layout="vertical"
              size="large"
            >
              <Form.Item
                name="email"
                rules={[
                  { required: true, message: '请输入邮箱地址' },
                  { type: 'email', message: '请输入有效的邮箱地址' }
                ]}
              >
                <Input 
                  prefix={<UserOutlined />} 
                  placeholder="请输入您的邮箱地址" 
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
                  发送重置邮件
                </Button>
              </Form.Item>
            </Form>
            
            <div className="text-center mt-6">
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                如果您没有收到邮件，请检查垃圾邮件文件夹<br/>
                或者联系系统管理员
              </Paragraph>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
