import React, { useState, useEffect } from 'react';
import {
  Layout, Typography, Button, Card, Table, Tag, Space,
  Modal, message, Empty, Row, Col, Statistic
} from 'antd';
import {
  EyeOutlined, DeleteOutlined,
  BarChartOutlined, RocketOutlined, FileTextOutlined
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { reportService, Report } from '../../../services/report.service';

const { Title } = Typography;

interface ReportsPageProps {
  projectId?: string;
}

const ReportsPage: React.FC<ReportsPageProps> = ({ projectId: propProjectId }) => {
  const { id: urlProjectId } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 优先使用props传入的projectId，否则使用URL中的
  const projectId = propProjectId || urlProjectId;

  useEffect(() => {
    if (projectId) {
      fetchReports();
    }
  }, [projectId]);

  const fetchReports = async () => {
    setLoading(true);
    try {
      const data = await reportService.getProjectReports(projectId!);
      setReports(data);
    } catch (error) {
      console.error('获取报告列表失败:', error);
      message.error('获取报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleViewReport = (reportId: string) => {
    navigate(`/projects/${projectId}/reports/${reportId}`);
  };

  // 移除导出功能，在详情页中提供

  // 移除Markdown生成函数，在详情页中提供

  // 移除分享功能

  const getReportTypeIcon = (type: string) => {
    switch (type) {
      case 'evaluation': return <BarChartOutlined />;
      case 'performance': return <RocketOutlined />;
      case 'comparison': return <FileTextOutlined />;
      default: return <FileTextOutlined />;
    }
  };

  const getReportTypeName = (type: string) => {
    switch (type) {
      case 'evaluation': return '评测报告';
      case 'performance': return '性能报告';
      case 'comparison': return '对比报告';
      default: return '未知类型';
    }
  };

  return (
    <Layout.Content style={{ padding: '24px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Title level={3}>评测报告</Title>
        <div style={{ color: '#666', fontSize: '14px' }}>
          报告基于评测结果自动生成，无需手动创建
        </div>
      </div>

      {reports.length > 0 ? (
        <Table
          dataSource={reports}
          rowKey="id"
          loading={loading}
          columns={[
            {
              title: '报告名称',
              dataIndex: 'title',
              key: 'title',
              width: 200,
            },
            {
              title: '类型',
              dataIndex: 'report_type',
              key: 'report_type',
              width: 120,
              render: (type) => (
                <Tag icon={getReportTypeIcon(type)}>
                  {getReportTypeName(type)}
                </Tag>
              )
            },
            {
              title: '描述',
              dataIndex: 'description',
              key: 'description',
              ellipsis: true,
              width: 250,
            },
            {
              title: '公开',
              dataIndex: 'public',
              key: 'public',
              width: 80,
              render: (isPublic) => (
                <Tag color={isPublic ? 'green' : 'default'}>
                  {isPublic ? '公开' : '私有'}
                </Tag>
              )
            },
            {
              title: '创建时间',
              dataIndex: 'created_at',
              key: 'created_at',
              width: 180,
              render: (time) => new Date(time).toLocaleString()
            },
            {
              title: '操作',
              key: 'action',
              width: 200,
              render: (_, record) => (
                <Space>
                  <Button
                    type="primary"
                    icon={<EyeOutlined />}
                    onClick={() => handleViewReport(record.id)}
                  >
                    查看详情
                  </Button>
                  {/* 只有手动创建的报告才显示删除按钮 */}
                  {record.config?.manual_created && (
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => {
                        Modal.confirm({
                          title: '确定要删除此报告吗？',
                          content: '删除后无法恢复',
                          onOk: async () => {
                            try {
                              await reportService.deleteReport(record.id);
                              message.success('报告已删除');
                              fetchReports();
                            } catch (error) {
                              message.error('删除报告失败');
                            }
                          }
                        });
                      }}
                    >
                      删除
                    </Button>
                  )}
                </Space>
              )
            }
          ]}
        />
      ) : (
        <Empty
          description="暂无报告"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        >
          <div style={{ color: '#666', fontSize: '14px' }}>
            完成评测后将自动生成报告
          </div>
        </Empty>
      )}
    </Layout.Content>
  );
};

export default ReportsPage;
