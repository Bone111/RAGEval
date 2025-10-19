import React, { useState, useEffect } from 'react';
import { Alert, Button, Space, Badge, Modal, message, Upload } from 'antd';
import { CloudOutlined, ExportOutlined, ReloadOutlined, ImportOutlined } from '@ant-design/icons';
import { ConfigManager } from '../utils/configManager';

const ConfigStorageStatus: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [serverStatus, setServerStatus] = useState<'unknown' | 'connected' | 'disconnected'>('unknown');
  
  const configManager = ConfigManager.getInstance();

  const checkStatus = async () => {
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
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        setServerStatus('connected');
      } else {
        setServerStatus('disconnected');
      }
    } catch (error) {
      console.log('服务器连接检查失败:', error);
      setServerStatus('disconnected');
    }
  };

  useEffect(() => {
    checkStatus();
    
    // 定期检查服务器状态
    const interval = setInterval(checkStatus, 30000); // 30秒检查一次
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = async () => {
    setIsLoading(true);
    try {
      await checkStatus();
      message.success('状态已刷新');
    } catch (error) {
      message.error('刷新失败');
    } finally {
      setIsLoading(false);
    }
  };

  const handleExport = async () => {
    try {
      const configs = await configManager.exportAllConfigs();
      const dataStr = JSON.stringify(configs, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      
      const link = document.createElement('a');
      link.href = URL.createObjectURL(dataBlob);
      link.download = `rag_eval_configs_${new Date().toISOString().split('T')[0]}.json`;
      link.click();
      
      message.success('配置导出成功');
    } catch (error) {
      message.error('配置导出失败: ' + error);
    }
  };

  const handleImport = async (file: File) => {
    try {
      const text = await file.text();
      const configs = JSON.parse(text);
      
      await configManager.importConfigs(configs);
      message.success('配置导入成功');
      
      // 刷新状态
      await checkStatus();
    } catch (error) {
      message.error('配置导入失败: ' + error);
    }
  };

  const getStatusInfo = () => {
    if (serverStatus === 'disconnected') {
      return {
        type: 'error' as const,
        icon: <CloudOutlined />,
        text: '服务器连接失败',
        description: '无法连接到后端服务，请检查后端服务是否启动'
      };
    }
    
    return {
      type: 'success' as const,
      icon: <CloudOutlined />,
      text: '云端存储',
      description: '配置已保存到服务器，不会因为清理浏览器缓存而丢失'
    };
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
              <strong>{statusInfo.text}</strong>
              <div style={{ fontSize: '12px', color: '#666', marginTop: 4 }}>
                {statusInfo.description}
              </div>
            </div>
            
            <Space size="small">
              {/* 导出配置 */}
              <Button 
                type="link" 
                size="small" 
                icon={<ExportOutlined />}
                onClick={handleExport}
              >
                导出
              </Button>

              {/* 导入配置 */}
              <Upload
                accept=".json"
                showUploadList={false}
                beforeUpload={handleImport}
              >
                <Button 
                  type="link" 
                  size="small" 
                  icon={<ImportOutlined />}
                >
                  导入
                </Button>
              </Upload>

              {/* 刷新状态 */}
              <Button 
                type="link" 
                size="small" 
                icon={<ReloadOutlined />}
                loading={isLoading}
                onClick={handleRefresh}
              >
                刷新状态
              </Button>
            </Space>
          </div>
        }
        style={{ borderRadius: 6 }}
      />
    </div>
  );
};

export default ConfigStorageStatus;