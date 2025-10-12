import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Row,
  Col,
  Typography,
  Input,
  Select,
  Tag,
  Button,
  Space,
  Descriptions,
  Modal,
  Badge,
  Tooltip,
  Statistic,
  Progress,
  Avatar,
  message,
  Spin
} from 'antd';
import {
  ArrowLeftOutlined,
  SearchOutlined,
  FireOutlined,
  StarOutlined,
  PlayCircleOutlined,
  InfoCircleOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  BugOutlined,
  PictureOutlined,
  CalculatorOutlined,
  BookOutlined,
  GlobalOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  SyncOutlined,
  ReloadOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  AppstoreOutlined,
  UnorderedListOutlined
} from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const { Search } = Input;
const { Option } = Select;

interface BenchmarkInfo {
  name: string;
  display_name: string;
  description: string;
  category: string;
  language: string;
  num_samples: number;
  tags: string[];
  cached: boolean;
  cache_status: 'not_cached' | 'downloading' | 'cached' | 'error';
  download_progress?: number;
  file_size?: string;
  last_updated?: string;
}

const BenchmarkHubPage: React.FC = () => {
  const navigate = useNavigate();
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedLanguage, setSelectedLanguage] = useState<string>('all');
  const [sortBy, setSortBy] = useState<string>('name'); // name, category, cached, popularity
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [searchQuery, setSearchQuery] = useState('');
  const [benchmarks, setBenchmarks] = useState<BenchmarkInfo[]>([]);
  const [selectedBenchmark, setSelectedBenchmark] = useState<BenchmarkInfo | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [downloadingBenchmarks, setDownloadingBenchmarks] = useState<Set<string>>(new Set());

  // API 调用函数
  const fetchBenchmarks = async (category?: string, language?: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (category && category !== 'all') params.append('category', category);
      if (language && language !== 'all') params.append('language', language);
      
      const response = await fetch(`/api/v1/evalscope/benchmarks?${params}`);
      if (!response.ok) throw new Error('获取benchmark列表失败');
      
      const data = await response.json();
      setBenchmarks(data.benchmarks || []);
    } catch (error) {
      console.error('获取benchmarks失败:', error);
      message.error('获取benchmark列表失败');
    } finally {
      setLoading(false);
    }
  };

  const downloadBenchmark = async (benchmarkName: string) => {
    setDownloadingBenchmarks(prev => new Set([...prev, benchmarkName]));
    
    try {
      const response = await fetch('/api/v1/evalscope/benchmarks/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          benchmark_names: [benchmarkName],
          force_redownload: false
        })
      });
      
      if (!response.ok) throw new Error('下载请求失败');
      
      const result = await response.json();
      
      if (result.started_downloads?.includes(benchmarkName)) {
        message.success(`已开始下载 ${benchmarkName}`);
        // 立即更新状态为downloading
        setBenchmarks(prev => prev.map(b => 
          b.name === benchmarkName ? { ...b, cache_status: 'downloading', download_progress: 0 } : b
        ));
        // 开始轮询状态更新
        pollBenchmarkStatus(benchmarkName);
      } else if (result.already_cached?.includes(benchmarkName)) {
        message.info(`${benchmarkName} 已缓存`);
        // 立即刷新列表以获取最新状态
        fetchBenchmarks(selectedCategory);
      } else if (result.failed_downloads?.some(f => f.name === benchmarkName)) {
        const failedItem = result.failed_downloads.find(f => f.name === benchmarkName);
        message.error(`下载失败: ${failedItem?.error || '未知错误'}`);
      } else {
        message.error(result.message || '下载失败');
      }
      
    } catch (error) {
      console.error('下载失败:', error);
      message.error('下载请求失败');
    } finally {
      setDownloadingBenchmarks(prev => {
        const next = new Set(prev);
        next.delete(benchmarkName);
        return next;
      });
    }
  };

  const downloadAllBenchmarks = async () => {
    const uncachedBenchmarks = benchmarks.filter(b => !b.cached);
    if (uncachedBenchmarks.length === 0) {
      message.info('所有基准测试已缓存');
      return;
    }

    Modal.confirm({
      title: '确认下载所有基准测试',
      content: `将下载 ${uncachedBenchmarks.length} 个未缓存的基准测试，这可能需要较长时间。是否继续？`,
      onOk: async () => {
        try {
          const response = await fetch('/api/v1/evalscope/benchmarks/download-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              force_redownload: false
            })
          });
          
          if (!response.ok) throw new Error('下载请求失败');
          
          const result = await response.json();
          
          if (result.started_downloads?.length > 0) {
            message.success(`已开始下载 ${result.started_downloads.length} 个基准测试`);
            // 更新所有下载中的基准测试状态
            setBenchmarks(prev => prev.map(b => 
              result.started_downloads.includes(b.name) 
                ? { ...b, cache_status: 'downloading', download_progress: 0 } 
                : b
            ));
            // 开始轮询所有下载中的基准测试状态
            result.started_downloads.forEach((name: string) => {
              pollBenchmarkStatus(name);
            });
          }
          
          if (result.already_cached?.length > 0) {
            message.info(`${result.already_cached.length} 个基准测试已缓存`);
          }
          
          if (result.failed_downloads?.length > 0) {
            message.warning(`${result.failed_downloads.length} 个基准测试下载失败`);
          }
          
        } catch (error) {
          console.error('批量下载失败:', error);
          message.error('批量下载请求失败');
        }
      }
    });
  };

  const pollBenchmarkStatus = async (benchmarkName: string) => {
    const maxAttempts = 60; // 增加轮询次数到60次（2分钟）
    let attempts = 0;
    
    const poll = async () => {
      if (attempts >= maxAttempts) {
        message.warning(`${benchmarkName} 下载超时，请手动检查状态`);
        return;
      }
      attempts++;
      
      try {
        const response = await fetch(`/api/v1/evalscope/benchmarks/${benchmarkName}/status`);
        if (!response.ok) {
          console.error(`获取 ${benchmarkName} 状态失败: ${response.status}`);
          return;
        }
        
        const status = await response.json();
        
        // 更新本地状态
        setBenchmarks(prev => prev.map(b => 
          b.name === benchmarkName ? { ...b, ...status } : b
        ));
        
        if (status.cache_status === 'cached') {
          message.success(`${benchmarkName} 下载完成`);
          return;
        } else if (status.cache_status === 'error') {
          message.error(`${benchmarkName} 下载失败: ${status.error_message || '未知错误'}`);
          return;
        } else if (status.cache_status === 'downloading') {
          // 继续轮询，间隔时间逐渐增加
          const delay = Math.min(2000 + attempts * 500, 5000); // 2-5秒间隔
          setTimeout(poll, delay);
        } else {
          // 未知状态，继续轮询
          setTimeout(poll, 3000);
        }
      } catch (error) {
        console.error(`获取 ${benchmarkName} 状态失败:`, error);
        // 网络错误时继续尝试
        if (attempts < maxAttempts) {
          setTimeout(poll, 5000);
        }
      }
    };
    
    setTimeout(poll, 1000);
  };

  // 初始化加载数据
  useEffect(() => {
    fetchBenchmarks(selectedCategory);
  }, [selectedCategory]);

  // 处理分类变化
  const handleCategoryChange = (category: string) => {
    setSelectedCategory(category);
  };

  // 计算热度分数
  const calculatePopularityScore = (benchmark: BenchmarkInfo) => {
    let score = 0;
    
    // 基础分数
    score += 10;
    
    // 已缓存加分
    if (benchmark.cached) score += 20;
    
    // 热门标签加分
    const hotTags = ['热门', '权威', 'general', 'knowledge', 'math', 'reasoning'];
    const hasHotTags = benchmark.tags?.some(tag => 
      hotTags.some(hotTag => tag.toLowerCase().includes(hotTag))
    );
    if (hasHotTags) score += 15;
    
    // 样本数量加分（样本越多越重要）
    if (benchmark.num_samples) {
      score += Math.min(benchmark.num_samples / 1000, 10);
    }
    
    // 多模态加分
    if (benchmark.tags?.some(tag => tag.includes('多模态') || tag.includes('vision'))) {
      score += 5;
    }
    
    return score;
  };

  const filteredBenchmarks = benchmarks.filter(benchmark => {
    const matchesCategory = selectedCategory === 'all' || benchmark.category === selectedCategory;
    const matchesLanguage = selectedLanguage === 'all' || benchmark.language === selectedLanguage;
    const matchesSearch = searchQuery === '' || 
      benchmark.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      benchmark.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      benchmark.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      benchmark.tags?.some(tag => tag.toLowerCase().includes(searchQuery.toLowerCase()));
    
    return matchesCategory && matchesLanguage && matchesSearch;
  });

  // 排序逻辑
  const sortedBenchmarks = [...filteredBenchmarks].sort((a, b) => {
    let comparison = 0;
    
    switch (sortBy) {
      case 'name':
        comparison = a.display_name.localeCompare(b.display_name);
        break;
      case 'category':
        comparison = a.category.localeCompare(b.category);
        break;
      case 'cached':
        comparison = (b.cached ? 1 : 0) - (a.cached ? 1 : 0);
        break;
      case 'popularity':
        comparison = calculatePopularityScore(b) - calculatePopularityScore(a);
        break;
      case 'samples':
        comparison = (b.num_samples || 0) - (a.num_samples || 0);
        break;
      default:
        comparison = 0;
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  const categories = ['all', ...Array.from(new Set(benchmarks.map(b => b.category)))];

  // 获取缓存状态的显示组件
  const getCacheStatusIcon = (status: string) => {
    switch (status) {
      case 'cached':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'downloading':
        return <SyncOutlined spin style={{ color: '#1890ff' }} />;
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />;
      default:
        return <DownloadOutlined style={{ color: '#8c8c8c' }} />;
    }
  };

  const getCacheStatusText = (status: string) => {
    switch (status) {
      case 'cached': return '已缓存';
      case 'downloading': return '下载中';
      case 'error': return '下载失败';
      default: return '未缓存';
    }
  };

  const handleStartEval = (benchmark: BenchmarkInfo) => {
    if (!benchmark.cached) {
      message.warning('请先下载该benchmark');
      return;
    }
    
    // 根据benchmark类型导航到不同页面
    if (benchmark.tags.includes('多模态') || benchmark.tags.includes('视觉')) {
      navigate('/evalscope/vlm', { state: { selectedDataset: benchmark.name } });
    } else {
      navigate('/evalscope/tasks/create', { state: { selectedDataset: benchmark.name } });
    }
  };

  const handleDownloadClick = (benchmark: BenchmarkInfo) => {
    if (benchmark.cached) {
      handleStartEval(benchmark);
    } else {
      downloadBenchmark(benchmark.name);
    }
  };

  return (
    <Spin spinning={loading}>
    <div style={{ padding: '24px' }}>
      {/* 头部 */}
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
              <FireOutlined /> Benchmark Hub
            </Title>
            <Text type="secondary">发现和探索各种评测基准</Text>
          </Space>
        </Col>
      </Row>

      {/* 统计概览 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总基准测试数"
              value={benchmarks.length}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
                title="已缓存"
                value={benchmarks.filter(b => b.cached).length}
                prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
                title="下载中"
                value={benchmarks.filter(b => b.cache_status === 'downloading').length}
                prefix={<SyncOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="支持语言"
                value={Array.from(new Set(benchmarks.map(b => b.language))).length + "+"}
              prefix={<GlobalOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 过滤控制 */}
      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Search
              placeholder="搜索基准测试名称、描述或标签"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              prefix={<SearchOutlined />}
              allowClear
            />
          </Col>
          <Col span={3}>
            <Select
              value={selectedCategory}
              onChange={handleCategoryChange}
              style={{ width: '100%' }}
              placeholder="类别"
            >
              <Option value="all">所有类别</Option>
              {categories.slice(1).map(cat => (
                <Option key={cat} value={cat}>{cat}</Option>
              ))}
            </Select>
          </Col>
          <Col span={3}>
            <Select
              value={selectedLanguage}
              onChange={setSelectedLanguage}
              style={{ width: '100%' }}
              placeholder="语言"
            >
              <Option value="all">所有语言</Option>
              <Option value="English">英语</Option>
              <Option value="Chinese">中文</Option>
            </Select>
          </Col>
          <Col span={3}>
            <Select
              value={sortBy}
              onChange={setSortBy}
              style={{ width: '100%' }}
              placeholder="排序"
            >
              <Option value="popularity">热度</Option>
              <Option value="name">名称</Option>
              <Option value="category">类别</Option>
              <Option value="cached">缓存状态</Option>
              <Option value="samples">样本数</Option>
            </Select>
          </Col>
          <Col span={2}>
            <Button 
              icon={sortOrder === 'asc' ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              title={`当前排序: ${sortOrder === 'asc' ? '升序' : '降序'}`}
            />
          </Col>
          <Col span={2}>
            <Button.Group>
              <Button 
                icon={<AppstoreOutlined />}
                type={viewMode === 'grid' ? 'primary' : 'default'}
                onClick={() => setViewMode('grid')}
                title="网格视图"
              />
              <Button 
                icon={<UnorderedListOutlined />}
                type={viewMode === 'list' ? 'primary' : 'default'}
                onClick={() => setViewMode('list')}
                title="列表视图"
              />
            </Button.Group>
          </Col>
          <Col span={2}>
            <Button 
              icon={<ReloadOutlined />}
              onClick={() => fetchBenchmarks(selectedCategory, selectedLanguage)}
              title="刷新数据"
            />
          </Col>
          <Col span={3}>
            <Button 
              type="primary"
              icon={<DownloadOutlined />}
              onClick={downloadAllBenchmarks}
              title="一键下载所有基准测试"
            >
              一键下载
            </Button>
          </Col>
          <Col span={3}>
            <Space>
              <Text type="secondary">
                找到 {sortedBenchmarks.length} 个基准测试
              </Text>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Benchmark列表 */}
      <Row gutter={[16, 16]}>
        {sortedBenchmarks.map(benchmark => {
          const popularityScore = calculatePopularityScore(benchmark);
          const isHot = popularityScore > 30;
          
          return viewMode === 'grid' ? (
            <Col span={8} key={benchmark.name}>
            <Card
              hoverable
              actions={[
                <Button 
                  type="text" 
                  icon={<EyeOutlined />}
                  onClick={() => {
                    setSelectedBenchmark(benchmark);
                    setModalVisible(true);
                  }}
                >
                  详情
                </Button>,
                <Button 
                    type={benchmark.cached ? "primary" : "default"}
                    icon={benchmark.cached ? <PlayCircleOutlined /> : <DownloadOutlined />}
                    loading={downloadingBenchmarks.has(benchmark.name)}
                    onClick={() => handleDownloadClick(benchmark)}
                  >
                    {benchmark.cached ? '开始评测' : '下载'}
                </Button>
              ]}
              cover={
                <div style={{ 
                  height: 120, 
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                    color: 'white',
                    position: 'relative'
                }}>
                  <Space direction="vertical" align="center">
                    <Avatar 
                      size={48} 
                      style={{ backgroundColor: 'rgba(255,255,255,0.2)' }}
                        icon={getCacheStatusIcon(benchmark.cache_status)}
                    />
                    <Text style={{ color: 'white', fontWeight: 'bold' }}>
                      {benchmark.display_name}
                    </Text>
                  </Space>
                    {/* 热度角标 */}
                    {isHot && (
                      <div style={{ 
                        position: 'absolute', 
                        top: 8, 
                        left: 8,
                        backgroundColor: '#ff4d4f',
                        borderRadius: '50%',
                        width: 24,
                        height: 24,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '12px',
                        fontWeight: 'bold'
                      }}>
                        🔥
                      </div>
                    )}
                    {/* 缓存状态角标 */}
                    <div style={{ 
                      position: 'absolute', 
                      top: 8, 
                      right: 8,
                      backgroundColor: 'rgba(0,0,0,0.6)',
                      borderRadius: 4,
                      padding: '2px 6px'
                    }}>
                      <Text style={{ color: 'white', fontSize: 12 }}>
                        {getCacheStatusText(benchmark.cache_status)}
                      </Text>
                    </div>
                </div>
              }
            >
              <Card.Meta
                title={
                  <Space>
                    <Text strong>{benchmark.name}</Text>
                      {benchmark.file_size && (
                        <Tag color="blue">{benchmark.file_size}</Tag>
                      )}
                  </Space>
                }
                description={
                  <div style={{ height: 60, overflow: 'hidden' }}>
                    <Paragraph ellipsis={{ rows: 2 }} style={{ marginBottom: 8 }}>
                      {benchmark.description}
                    </Paragraph>
                  </div>
                }
              />
              
              <div style={{ marginTop: 12 }}>
                <Space wrap>
                    <Tag>{benchmark.category}</Tag>
                    <Tag>{benchmark.language}</Tag>
                  <Tag>{benchmark.num_samples} 样本</Tag>
                  {isHot && <Tag color="red" icon={<FireOutlined />}>热门</Tag>}
                </Space>
              </div>

                {benchmark.cache_status === 'downloading' && (
                <div style={{ marginTop: 12 }}>
                  <Progress 
                      percent={benchmark.download_progress || 0}
                    size="small"
                      status="active"
                      format={(percent) => `${percent || 0}%`}
                  />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    正在下载 {benchmark.name}...
                  </Text>
                </div>
              )}

              <div style={{ marginTop: 8 }}>
                  <Space wrap>
                    {benchmark.tags.slice(0, 3).map(tag => (
                      <Tag key={tag}>{tag}</Tag>
                    ))}
                  </Space>
              </div>
            </Card>
          </Col>
          ) : (
            // 列表视图
            <Col span={24} key={benchmark.name}>
              <Card 
                hoverable
                style={{ marginBottom: 16 }}
                actions={[
                  <Button 
                    type="text" 
                    icon={<EyeOutlined />}
                    onClick={() => {
                      setSelectedBenchmark(benchmark);
                      setModalVisible(true);
                    }}
                  >
                    详情
                  </Button>,
                  <Button 
                    type={benchmark.cached ? "primary" : "default"}
                    icon={benchmark.cached ? <PlayCircleOutlined /> : <DownloadOutlined />}
                    loading={downloadingBenchmarks.has(benchmark.name)}
                    onClick={() => handleDownloadClick(benchmark)}
                  >
                    {benchmark.cached ? '开始评测' : '下载'}
                  </Button>
                ]}
              >
                <Row align="middle" gutter={16}>
                  <Col span={2}>
                    <Avatar 
                      size={48} 
                      style={{ backgroundColor: '#1890ff' }}
                      icon={getCacheStatusIcon(benchmark.cache_status)}
                    />
                  </Col>
                  <Col span={6}>
                    <div>
                      <Text strong style={{ fontSize: 16 }}>{benchmark.display_name}</Text>
                      <br />
                      <Text type="secondary" code>{benchmark.name}</Text>
                    </div>
                  </Col>
                  <Col span={8}>
                    <Paragraph ellipsis={{ rows: 2 }} style={{ margin: 0 }}>
                      {benchmark.description}
                    </Paragraph>
                  </Col>
                  <Col span={4}>
                    <Space direction="vertical" size="small">
                      <Space wrap>
                        <Tag>{benchmark.category}</Tag>
                        <Tag>{benchmark.language}</Tag>
                        {isHot && <Tag color="red" icon={<FireOutlined />}>热门</Tag>}
                      </Space>
                      <Text type="secondary">{benchmark.num_samples} 样本</Text>
                    </Space>
                  </Col>
                  <Col span={4}>
                    <Space direction="vertical" align="center">
                      <Space>
                        {getCacheStatusIcon(benchmark.cache_status)}
                        <Text>{getCacheStatusText(benchmark.cache_status)}</Text>
                      </Space>
                      {benchmark.file_size && (
                        <Tag color="blue">{benchmark.file_size}</Tag>
                      )}
                    </Space>
                  </Col>
                </Row>
                
                {benchmark.cache_status === 'downloading' && (
                  <div style={{ marginTop: 12 }}>
                    <Progress 
                      percent={benchmark.download_progress || 0}
                      size="small"
                      status="active"
                      format={(percent) => `${percent || 0}%`}
                    />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      正在下载 {benchmark.name}...
                    </Text>
                  </div>
                )}
              </Card>
            </Col>
          );
        })}
      </Row>

      {/* 详情Modal */}
      <Modal
        title={selectedBenchmark?.display_name}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={[
          <Button key="cancel" onClick={() => setModalVisible(false)}>
            关闭
          </Button>,
          <Button 
              key="action" 
              type={selectedBenchmark?.cached ? "primary" : "default"}
              icon={selectedBenchmark?.cached ? <PlayCircleOutlined /> : <DownloadOutlined />}
              loading={selectedBenchmark && downloadingBenchmarks.has(selectedBenchmark.name)}
            onClick={() => {
              if (selectedBenchmark) {
                  handleDownloadClick(selectedBenchmark);
                setModalVisible(false);
              }
            }}
          >
              {selectedBenchmark?.cached ? '开始评测' : '下载'}
          </Button>
        ]}
        width={800}
      >
        {selectedBenchmark && (
          <div>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="基准测试ID" span={2}>
                <Text code>{selectedBenchmark.name}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="类别">
                {selectedBenchmark.category}
              </Descriptions.Item>
                <Descriptions.Item label="语言">
                  <Tag>{selectedBenchmark.language}</Tag>
              </Descriptions.Item>
                <Descriptions.Item label="缓存状态">
                  <Space>
                    {getCacheStatusIcon(selectedBenchmark.cache_status)}
                    <Text>{getCacheStatusText(selectedBenchmark.cache_status)}</Text>
                  </Space>
              </Descriptions.Item>
              <Descriptions.Item label="样本数量">
                {selectedBenchmark.num_samples.toLocaleString()}
              </Descriptions.Item>
                {selectedBenchmark.file_size && (
                  <Descriptions.Item label="文件大小" span={2}>
                    {selectedBenchmark.file_size}
              </Descriptions.Item>
                )}
              <Descriptions.Item label="标签" span={2}>
                <Space wrap>
                  {selectedBenchmark.tags.map(tag => (
                    <Tag key={tag}>{tag}</Tag>
                  ))}
                </Space>
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 16 }}>
              <Title level={4}>描述</Title>
              <Paragraph>{selectedBenchmark.description}</Paragraph>
            </div>

              {selectedBenchmark.cache_status === 'downloading' && (
              <div style={{ marginTop: 16 }}>
                  <Title level={4}>下载进度</Title>
                  <Progress 
                    percent={selectedBenchmark.download_progress || 0}
                    status="active"
                    format={(percent) => `${percent || 0}%`}
                  />
                  <Text type="secondary">
                    正在下载 {selectedBenchmark.name}，请耐心等待...
                  </Text>
              </div>
            )}

              {selectedBenchmark.last_updated && (
            <div style={{ marginTop: 16 }}>
                  <Text type="secondary">
                    最后更新: {new Date(selectedBenchmark.last_updated).toLocaleString()}
                  </Text>
            </div>
              )}
          </div>
        )}
      </Modal>
    </div>
    </Spin>
  );
};

export default BenchmarkHubPage;
