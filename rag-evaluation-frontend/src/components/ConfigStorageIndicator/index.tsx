import React, { useState, useEffect } from 'react';
import { Badge, Tooltip, Button, Space, message } from 'antd';
import { CloudOutlined, LaptopOutlined, SyncOutlined, ExportOutlined } from '@ant-design/icons';
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
          </Space>
        )}
      </Space>
    </div>
  );
};

export default ConfigStorageIndicator;
