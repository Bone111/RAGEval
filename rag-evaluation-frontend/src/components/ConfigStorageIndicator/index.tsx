import React, { useState, useEffect } from 'react';
import { Badge, Tooltip, Button, Space, message, Upload } from 'antd';
import { CloudOutlined, LaptopOutlined, SyncOutlined, ExportOutlined, ImportOutlined } from '@ant-design/icons';
import { ConfigManager } from '../../utils/configManager';
import { useConfigMigration } from '../../hooks/useConfigMigration';
import styles from './index.module.css';

interface ConfigStorageIndicatorProps {
  className?: string;
  showActions?: boolean; // 是否显示操作按钮
}

const ConfigStorageIndicator: React.FC<ConfigStorageIndicatorProps> = ({ 
  className = '', 
  showActions = true 
}) => {
  const [storageMode, setStorageMode] = useState<'server' | 'local'>('local');
  const [hasLocalConfigs, setHasLocalConfigs] = useState(false);
  
  const configManager = ConfigManager.getInstance();
  const {
    hasLocalConfigs: migrationHasLocal,
    performMigration,
    isMigrating,
    exportConfigs,
    enableServerStorage,
    getCurrentStorageMode,
    MigrationModal
  } = useConfigMigration();

  useEffect(() => {
    // 检查当前存储模式和本地配置状态
    const checkStatus = () => {
      const mode = getCurrentStorageMode();
      const hasLocal = configManager.hasLocalConfigs();
      setStorageMode(mode);
      setHasLocalConfigs(hasLocal);
    };

    checkStatus();
    
    // 定期检查状态变化
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleRetryServerStorage = async () => {
    enableServerStorage();
    const newMode = getCurrentStorageMode();
    setStorageMode(newMode);
    
    if (hasLocalConfigs) {
      message.info('检测到本地配置，请选择是否迁移到服务端');
    }
  };

  const handleMigration = async () => {
    try {
      await performMigration();
      // 迁移后重新检查状态
      setHasLocalConfigs(configManager.hasLocalConfigs());
    } catch (error) {
      message.error('配置迁移失败');
    }
  };

  const handleImportConfigs = async (file: File) => {
    try {
      // 读取文件内容
      const text = await file.text();
      const configData = JSON.parse(text);
      
      // 验证文件格式
      if (!configData.models || !configData.rags || !Array.isArray(configData.models) || !Array.isArray(configData.rags)) {
        throw new Error('配置文件格式不正确');
      }
      
      // 导入配置
      const result = await configManager.importConfigs(configData);
      
      // 显示导入结果
      if (result.failed === 0) {
        message.success(`配置导入成功！共导入 ${result.success} 个配置`);
      } else {
        message.warning(`配置导入完成！成功 ${result.success} 个，失败 ${result.failed} 个`);
      }
      
      // 重新检查状态
      setHasLocalConfigs(configManager.hasLocalConfigs());
      
      // 触发配置变化事件，通知其他组件刷新
      window.dispatchEvent(new CustomEvent('configChanged'));
      
      return false; // 阻止默认上传行为
    } catch (error) {
      message.error('配置导入失败: ' + error);
      return false;
    }
  };

  const getStatusInfo = () => {
    if (storageMode === 'server') {
      return {
        icon: <CloudOutlined />,
        text: '云端存储',
        color: 'success' as const,
        description: '配置已保存到服务器，不会因为清理浏览器缓存而丢失'
      };
    } else {
      return {
        icon: <LaptopOutlined />,
        text: '本地存储',
        color: 'warning' as const,
        description: '配置保存在浏览器中，清理缓存时会丢失。建议迁移到云端存储'
      };
    }
  };

  const statusInfo = getStatusInfo();

  return (
    <div className={`${styles.container} ${className}`}>
      <MigrationModal />
      
      <Space size="middle" align="center">
        <Tooltip title={statusInfo.description}>
          <Badge 
            status={statusInfo.color}
            text={
              <Space size="small">
                {statusInfo.icon}
                <span className={styles.statusText}>{statusInfo.text}</span>
              </Space>
            }
          />
        </Tooltip>

        {showActions && (
          <Space size="small">
            {/* 本地存储模式下的操作 */}
            {storageMode === 'local' && (
              <>
                <Tooltip title="尝试重新连接服务端存储">
                  <Button 
                    type="link" 
                    size="small" 
                    icon={<CloudOutlined />}
                    onClick={handleRetryServerStorage}
                  >
                    切换云端
                  </Button>
                </Tooltip>
                
                {hasLocalConfigs && (
                  <Tooltip title="将本地配置迁移到服务端">
                    <Button 
                      type="link" 
                      size="small" 
                      icon={<SyncOutlined />}
                      loading={isMigrating}
                      onClick={handleMigration}
                    >
                      迁移配置
                    </Button>
                  </Tooltip>
                )}
              </>
            )}

            {/* 云端存储模式下的操作 */}
            {storageMode === 'server' && hasLocalConfigs && (
              <Tooltip title="仍有本地配置未迁移">
                <Button 
                  type="link" 
                  size="small" 
                  icon={<SyncOutlined />}
                  loading={isMigrating}
                  onClick={handleMigration}
                  style={{ color: '#faad14' }}
                >
                  迁移剩余配置
                </Button>
              </Tooltip>
            )}

            {/* 导出配置 */}
            <Tooltip title="导出配置备份">
              <Button 
                type="link" 
                size="small" 
                icon={<ExportOutlined />}
                onClick={exportConfigs}
              >
                导出
              </Button>
            </Tooltip>

            {/* 导入配置 */}
            <Upload
              accept=".json"
              showUploadList={false}
              beforeUpload={handleImportConfigs}
            >
              <Tooltip title="导入配置备份">
                <Button 
                  type="link" 
                  size="small" 
                  icon={<ImportOutlined />}
                >
                  导入
                </Button>
              </Tooltip>
            </Upload>
          </Space>
        )}
      </Space>
    </div>
  );
};

export default ConfigStorageIndicator;
