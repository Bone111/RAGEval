import React from 'react';
import { Button, Space, message, Upload } from 'antd';
import { ExportOutlined, ImportOutlined } from '@ant-design/icons';
import { ConfigManager } from '../../utils/configManager';
import { useConfigMigration } from '../../hooks/useConfigMigration';

interface ConfigStorageIndicatorProps {
  className?: string;
  showActions?: boolean; // 是否显示操作按钮
}

const ConfigStorageIndicator: React.FC<ConfigStorageIndicatorProps> = ({ 
  className = '', 
  showActions = true 
}) => {
  const configManager = ConfigManager.getInstance();
  const {
    exportConfigs
  } = useConfigMigration();

  const handleExport = async () => {
    try {
      await exportConfigs();
      message.success('配置导出成功');
    } catch (error) {
      message.error('配置导出失败');
    }
  };

  const handleImport = (file: any) => {
    // 导入逻辑
    console.log('导入文件:', file);
    message.info('导入功能开发中...');
    return false;
  };

  if (!showActions) {
    return null;
  }

  return (
    <div className={className}>
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
      </Space>
    </div>
  );
};

export default ConfigStorageIndicator;