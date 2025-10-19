import React, { useEffect, useState } from 'react';
import { Table, Input, Space, Tag, Typography, Spin, Button, Modal, Form, message } from 'antd';
import { SearchOutlined, KeyOutlined } from '@ant-design/icons';
import { adminService } from '../../services/admin.service';

const { Title } = Typography;

interface User {
  id: string;
  name: string;
  email: string;
  company: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchText, setSearchText] = useState<string>('');
  const [resetPasswordModalVisible, setResetPasswordModalVisible] = useState<boolean>(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [resetPasswordForm] = Form.useForm();

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        const data = await adminService.getUsers();
        setUsers(data);
      } catch (error) {
        console.error('获取用户列表失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, []);

  const handleResetPassword = (user: User) => {
    setSelectedUser(user);
    setResetPasswordModalVisible(true);
    resetPasswordForm.resetFields();
  };

  const handleResetPasswordSubmit = async (values: { newPassword: string; confirmPassword: string }) => {
    if (values.newPassword !== values.confirmPassword) {
      message.error('两次输入的密码不一致');
      return;
    }

    if (!selectedUser) return;

    try {
      await adminService.resetUserPassword(selectedUser.id, values.newPassword);
      setResetPasswordModalVisible(false);
      setSelectedUser(null);
      resetPasswordForm.resetFields();
      // 刷新用户列表
      const data = await adminService.getUsers();
      setUsers(data);
    } catch (error) {
      console.error('重置密码失败:', error);
    }
  };

  const columns = [
    {
      title: '用户名',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '公司',
      dataIndex: 'company',
      key: 'company',
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: User) => (
        <Space>
          {record.is_active ? (
            <Tag color="green">活跃</Tag>
          ) : (
            <Tag color="red">停用</Tag>
          )}
          {record.is_admin && (
            <Tag color="blue">管理员</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleString(),
      sorter: (a: User, b: User) => 
        new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: User) => (
        <Space>
          <Button
            type="primary"
            size="small"
            icon={<KeyOutlined />}
            onClick={() => handleResetPassword(record)}
          >
            重置密码
          </Button>
        </Space>
      ),
    },
  ];

  const filteredUsers = users.filter(
    user => 
      user.name?.toLowerCase().includes(searchText.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchText.toLowerCase()) ||
      user.company?.toLowerCase().includes(searchText.toLowerCase())
  );

  return (
<div style={{marginTop:30}}>
      <Title level={2}>用户管理</Title>
      
      <div style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索用户名、邮箱或公司"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={e => setSearchText(e.target.value)}
          style={{ width: 300 }}
        />
      </div>
      
      {loading ? (
        <Spin size="large" />
      ) : (
        <Table
          columns={columns}
          dataSource={filteredUsers}
          rowKey="id"
          pagination={{ pageSize: 10 }}
        />
      )}

      <Modal
        title={`重置用户 ${selectedUser?.name} 的密码`}
        open={resetPasswordModalVisible}
        onCancel={() => {
          setResetPasswordModalVisible(false);
          setSelectedUser(null);
          resetPasswordForm.resetFields();
        }}
        footer={null}
      >
        <Form
          form={resetPasswordForm}
          layout="vertical"
          onFinish={handleResetPasswordSubmit}
        >
          <Form.Item
            label="新密码"
            name="newPassword"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '密码长度至少8位' }
            ]}
          >
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
          
          <Form.Item
            label="确认密码"
            name="confirmPassword"
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('newPassword') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
          
          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                确认重置
              </Button>
              <Button onClick={() => {
                setResetPasswordModalVisible(false);
                setSelectedUser(null);
                resetPasswordForm.resetFields();
              }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagement;
