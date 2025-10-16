import React, { useState, useEffect } from 'react';
import { Alert, Button, Space, Badge, Modal, message } from 'antd';
import { CloudOutlined, LaptopOutlined, SyncOutlined, ExportOutlined, ReloadOutlined } from '@ant-design/icons';
import { ConfigManager } from '../utils/configManager';

const ConfigStorageStatus: React.FC = () => {
  const [storageMode, setStorageMode] = useState<'server' | 'local'>('local');
  const [hasLocalConfigs, setHasLocalConfigs] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'unknown' | 'connected' | 'disconnected'>('unknown');
  
  const configManager = ConfigManager.getInstance();

  const checkStatus = async () => {
    const mode = configManager.getCurrentStorageMode();
    const hasLocal = configManager.hasLocalConfigs();
    setStorageMode(mode);
    setHasLocalConfigs(hasLocal);
    
    // 检测服务器连接状态
    await checkServerStatus();
  };

  const checkServerStatus = async () => {
    try {
      // 创建超时控制器
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000); // 3秒超时
      
      // 使用健康检查接口，不需要认证
      const response = await fetch('/api/v1/health', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        setServerStatus('connected');
        console.log('✅ 服务器连接正常');
      } else {
        setServerStatus('disconnected');
        console.warn('⚠️ 服务器响应异常:', response.status);
      }
    } catch (error) {
      console.warn('❌ 服务器连接检测失败:', error);
      setServerStatus('disconnected');
    }
  };

  useEffect(() => {
    // 立即检查一次状态
    checkStatus();
    
    // 设置定时检查，但频率稍微低一些
    const interval = setInterval(checkStatus, 10000); // 每10秒检查一次
    return () => clearInterval(interval);
  }, []);

  const handleRetryServerStorage = () => {
    configManager.enableServerStorage();
    checkStatus();
    message.info('已重新启用服务端存储');
  };

  const handleMigrateConfigs = async () => {
    setIsLoading(true);
    try {
      const result = await configManager.syncLocalConfigsToServer();
      
      if (result.failed === 0) {
        message.success(`成功同步 ${result.success} 个配置到服务端`);
      } else {
        Modal.warning({
          title: '部分配置同步失败',
          content: (
            <div>
              <p>成功同步: {result.success} 个配置</p>
              <p>失败: {result.failed} 个配置</p>
              <div style={{ marginTop: 16, maxHeight: 200, overflow: 'auto' }}>
                <p><strong>错误详情:</strong></p>
                <ul>
                  {result.errors.map((error, index) => (
                    <li key={index} style={{ fontSize: '12px', color: '#f5222d' }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ),
        });
      }
      
      checkStatus();
    } catch (error) {
      message.error('配置迁移失败: ' + error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportConfigs = async () => {
    try {
      const configs = await configManager.exportAllConfigs();
      const dataStr = JSON.stringify(configs, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      
      const link = document.createElement('a');
      link.href = URL.createObjectURL(dataBlob);
      link.download = `rag-eval-configs-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      message.success('配置导出成功');
    } catch (error) {
      message.error('配置导出失败: ' + error);
    }
  };

  const getStatusInfo = () => {
    if (serverStatus === 'disconnected') {
      return {
        type: 'error' as const,
        icon: <LaptopOutlined />,
        text: '服务器连接失败',
        description: '无法连接到后端服务，正在使用本地存储。请检查后端服务是否启动'
      };
    }
    
    if (storageMode === 'server' && serverStatus === 'connected') {
      return {
        type: 'success' as const,
        icon: <CloudOutlined />,
        text: '云端存储',
        description: '配置已保存到服务器，不会因为清理浏览器缓存而丢失'
      };
    } else {
      return {
        type: 'warning' as const,
        icon: <LaptopOutlined />,
        text: '本地存储',
        description: '配置保存在浏览器中，清理缓存时会丢失。建议迁移到云端存储'
      };
    }
  };

  const statusInfo = getStatusInfo();

  return (
    <div style={{ marginBottom: 16 }}>
      <Alert
        type={statusInfo.type}
        showIcon
        icon={statusInfo.icon}
        message={
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <Badge 
                status={statusInfo.type === 'success' ? 'success' : 'warning'} 
                text={statusInfo.text} 
              />
              <span style={{ marginLeft: 8, color: '#666' }}>
                {statusInfo.description}
              </span>
            </div>
            
            <Space size="small">
              {serverStatus === 'disconnected' && (
                <Button 
                  size="small" 
                  icon={<ReloadOutlined />}
                  onClick={async () => {
                    console.log('🔄 手动重新检测服务器连接...');
                    await checkServerStatus();
                    setTimeout(() => {
                      if (serverStatus === 'connected') {
                        handleRetryServerStorage();
                        message.success('服务器连接已恢复，已切换到云端存储');
                      } else {
                        message.warning('服务器仍无法连接，请检查后端服务');
                      }
                    }, 500);
                  }}
                  type="primary"
                  danger
                >
                  重新连接
                </Button>
              )}
              
              {storageMode === 'local' && serverStatus === 'connected' && (
                <>
                  <Button 
                    size="small" 
                    icon={<CloudOutlined />}
                    onClick={handleRetryServerStorage}
                  >
                    切换云端
                  </Button>
                  
                  {hasLocalConfigs && (
                    <Button 
                      size="small" 
                      icon={<SyncOutlined />}
                      loading={isLoading}
                      onClick={handleMigrateConfigs}
                    >
                      迁移配置
                    </Button>
                  )}
                </>
              )}
              
              {storageMode === 'server' && hasLocalConfigs && (
                <Button 
                  size="small" 
                  icon={<SyncOutlined />}
                  loading={isLoading}
                  onClick={handleMigrateConfigs}
                  type="primary"
                  style={{ backgroundColor: '#faad14', borderColor: '#faad14' }}
                >
                  迁移剩余配置
                </Button>
              )}
              
              <Button 
                size="small" 
                icon={<ExportOutlined />}
                onClick={handleExportConfigs}
              >
                导出
              </Button>
              
              <Button 
                size="small" 
                icon={<ReloadOutlined />}
                onClick={checkStatus}
              >
                刷新状态
              </Button>
              
              <Button 
                size="small"
                onClick={async () => {
                  try {
                    const status = await configManager.getDetailedStatus();
                    Modal.info({
                      title: '配置存储详细状态',
                      width: 600,
                      content: (
                        <div style={{ fontSize: 12, fontFamily: 'monospace' }}>
                          <pre>{JSON.stringify(status, null, 2)}</pre>
                        </div>
                      ),
                    });
                  } catch (error) {
                    message.error('获取状态失败: ' + error);
                  }
                }}
              >
                调试信息
              </Button>
            </Space>
          </div>
        }
      />
    </div>
  );
};

export default ConfigStorageStatus;
