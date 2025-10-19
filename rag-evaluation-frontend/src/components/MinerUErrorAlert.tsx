import React from 'react';
import { Alert, Button, Space } from 'antd';
import { ExclamationCircleOutlined, SettingOutlined, ReloadOutlined } from '@ant-design/icons';
import { mineruService, MinerUError } from '../services/mineruService';

interface MinerUErrorAlertProps {
  error: MinerUError;
  onRetry?: () => void;
  onConfigure?: () => void;
  style?: React.CSSProperties;
}

const MinerUErrorAlert: React.FC<MinerUErrorAlertProps> = ({
  error,
  onRetry,
  onConfigure,
  style
}) => {
  const getAlertType = (action: string) => {
    switch (action) {
      case 'configure_mineru':
        return 'warning';
      case 'check_key':
        return 'error';
      case 'retry':
        return 'info';
      default:
        return 'error';
    }
  };

  const getIcon = (action: string) => {
    switch (action) {
      case 'configure_mineru':
        return <SettingOutlined />;
      case 'check_key':
        return <ExclamationCircleOutlined />;
      case 'retry':
        return <ReloadOutlined />;
      default:
        return <ExclamationCircleOutlined />;
    }
  };

  const handleAction = () => {
    switch (error.action) {
      case 'configure_mineru':
        if (onConfigure) {
          onConfigure();
        } else if (error.redirect_to) {
          window.location.href = error.redirect_to;
        }
        break;
      case 'check_key':
        if (onConfigure) {
          onConfigure();
        } else if (error.redirect_to) {
          window.location.href = error.redirect_to;
        }
        break;
      case 'retry':
        if (onRetry) {
          onRetry();
        } else {
          window.location.reload();
        }
        break;
    }
  };

  const getActionButton = () => {
    const actionConfig = mineruService.getErrorAction(error);
    
    return (
      <Button
        type={actionConfig.type}
        icon={getIcon(error.action)}
        onClick={handleAction}
        size="small"
      >
        {actionConfig.text}
      </Button>
    );
  };

  return (
    <Alert
      message={error.error}
      description={
        <div>
          <div style={{ marginBottom: 8 }}>{error.message}</div>
          <Space>
            {getActionButton()}
            {error.action === 'retry' && onRetry && (
              <Button size="small" onClick={onRetry}>
                重试
              </Button>
            )}
          </Space>
        </div>
      }
      type={getAlertType(error.action)}
      showIcon
      style={style}
    />
  );
};

export default MinerUErrorAlert;
