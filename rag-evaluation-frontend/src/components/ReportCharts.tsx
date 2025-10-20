import React from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement,
} from 'chart.js';
import { Bar, Pie, Line } from 'react-chartjs-2';
import { Card, Row, Col } from 'antd';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  PointElement,
  LineElement
);

interface ReportChartsProps {
  reportType: string;
  content: any;
}

const ReportCharts: React.FC<ReportChartsProps> = ({ reportType, content }) => {
  if (reportType === 'evaluation') {
    return (
      <Row gutter={[16, 16]}>
        {/* 分数分布柱状图 */}
        {content.score_distribution && (
          <Col xs={24} md={12}>
            <Card title="分数分布" style={{ height: '400px' }}>
              <Bar
                data={{
                  labels: Object.keys(content.score_distribution),
                  datasets: [
                    {
                      label: '题目数量',
                      data: Object.values(content.score_distribution),
                      backgroundColor: 'rgba(54, 162, 235, 0.5)',
                      borderColor: 'rgba(54, 162, 235, 1)',
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'top' as const,
                    },
                    title: {
                      display: true,
                      text: '各分数段题目数量分布',
                    },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      ticks: {
                        stepSize: 1,
                      },
                    },
                  },
                }}
              />
            </Card>
          </Col>
        )}

        {/* 维度评分饼图 */}
        {content.dimensions && (
          <Col xs={24} md={12}>
            <Card title="维度评分分布" style={{ height: '400px' }}>
              <Pie
                data={{
                  labels: Object.keys(content.dimensions),
                  datasets: [
                    {
                      data: Object.values(content.dimensions).map((d: any) => d.average),
                      backgroundColor: [
                        'rgba(255, 99, 132, 0.5)',
                        'rgba(54, 162, 235, 0.5)',
                        'rgba(255, 205, 86, 0.5)',
                        'rgba(75, 192, 192, 0.5)',
                        'rgba(153, 102, 255, 0.5)',
                        'rgba(255, 159, 64, 0.5)',
                      ],
                      borderColor: [
                        'rgba(255, 99, 132, 1)',
                        'rgba(54, 162, 235, 1)',
                        'rgba(255, 205, 86, 1)',
                        'rgba(75, 192, 192, 1)',
                        'rgba(153, 102, 255, 1)',
                        'rgba(255, 159, 64, 1)',
                      ],
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'bottom' as const,
                    },
                    title: {
                      display: true,
                      text: '各维度平均评分',
                    },
                  },
                }}
              />
            </Card>
          </Col>
        )}

        {/* 完成率趋势图 */}
        {content.summary && (
          <Col xs={24}>
            <Card title="评测进度" style={{ height: '300px' }}>
              <Line
                data={{
                  labels: ['开始', '进行中', '完成'],
                  datasets: [
                    {
                      label: '完成率',
                      data: [
                        0,
                        content.summary.completion_rate * 0.7, // 模拟中间进度
                        content.summary.completion_rate,
                      ],
                      borderColor: 'rgba(75, 192, 192, 1)',
                      backgroundColor: 'rgba(75, 192, 192, 0.2)',
                      tension: 0.1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'top' as const,
                    },
                    title: {
                      display: true,
                      text: '评测完成率趋势',
                    },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      max: 1,
                      ticks: {
                        callback: function(value) {
                          return (value * 100).toFixed(0) + '%';
                        },
                      },
                    },
                  },
                }}
              />
            </Card>
          </Col>
        )}
      </Row>
    );
  }

  if (reportType === 'performance') {
    return (
      <Row gutter={[16, 16]}>
        {/* 响应时间分布 */}
        {content.time_distribution && (
          <Col xs={24} md={12}>
            <Card title="响应时间分布" style={{ height: '400px' }}>
              <Bar
                data={{
                  labels: Object.keys(content.time_distribution),
                  datasets: [
                    {
                      label: '请求数量',
                      data: Object.values(content.time_distribution),
                      backgroundColor: 'rgba(255, 99, 132, 0.5)',
                      borderColor: 'rgba(255, 99, 132, 1)',
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'top' as const,
                    },
                    title: {
                      display: true,
                      text: '各响应时间段的请求数量',
                    },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                    },
                  },
                }}
              />
            </Card>
          </Col>
        )}

        {/* 成功率饼图 */}
        {content.summary && (
          <Col xs={24} md={12}>
            <Card title="请求成功率" style={{ height: '400px' }}>
              <Pie
                data={{
                  labels: ['成功', '失败'],
                  datasets: [
                    {
                      data: [
                        content.summary.successful_requests,
                        content.summary.failed_requests,
                      ],
                      backgroundColor: [
                        'rgba(75, 192, 192, 0.5)',
                        'rgba(255, 99, 132, 0.5)',
                      ],
                      borderColor: [
                        'rgba(75, 192, 192, 1)',
                        'rgba(255, 99, 132, 1)',
                      ],
                      borderWidth: 1,
                    },
                  ],
                }}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: {
                      position: 'bottom' as const,
                    },
                    title: {
                      display: true,
                      text: '请求成功/失败分布',
                    },
                  },
                }}
              />
            </Card>
          </Col>
        )}
      </Row>
    );
  }

  return null;
};

export default ReportCharts;
