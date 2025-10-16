import { useState, useEffect } from 'react';
import { message, Modal } from 'antd';
import { ConfigManager } from '../utils/configManager';

interface MigrationState {
  hasLocalConfigs: boolean;
  isMigrating: boolean;
  migrationResult: {
    success: number;
    failed: number;
    errors: string[];
  } | null;
  showMigrationModal: boolean;
}

export function useConfigMigration() {
  const [state, setState] = useState<MigrationState>({
    hasLocalConfigs: false,
    isMigrating: false,
    migrationResult: null,
    showMigrationModal: false
  });

  const configManager = ConfigManager.getInstance();

  // 检查本地配置
  useEffect(() => {
    const checkLocalConfigs = () => {
      const hasLocal = configManager.hasLocalConfigs();
      setState(prev => ({ 
        ...prev, 
        hasLocalConfigs: hasLocal,
        showMigrationModal: hasLocal && configManager.getCurrentStorageMode() === 'server'
      }));
    };

    checkLocalConfigs();
  }, []);

  // 执行迁移
  const performMigration = async () => {
    setState(prev => ({ ...prev, isMigrating: true }));

    try {
      const result = await configManager.syncLocalConfigsToServer();
      
      setState(prev => ({ 
        ...prev, 
        isMigrating: false,
        migrationResult: result,
        hasLocalConfigs: result.failed > 0, // 如果有失败的，说明还有本地配置
        showMigrationModal: false
      }));

      if (result.failed === 0) {
        message.success(`成功同步 ${result.success} 个配置到服务端`);
      } else {
        message.warning(`同步完成：成功 ${result.success} 个，失败 ${result.failed} 个`);
        // 显示详细错误信息
        Modal.warning({
          title: '部分配置同步失败',
          content: (
            <div>
              <p>成功同步: {result.success} 个配置</p>
              <p>失败: {result.failed} 个配置</p>
              <div style={{ marginTop: 16 }}>
                <p><strong>错误详情:</strong></p>
                <ul style={{ maxHeight: 200, overflow: 'auto' }}>
                  {result.errors.map((error, index) => (
                    <li key={index} style={{ fontSize: '12px', color: '#f5222d' }}>
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ),
          width: 600
        });
      }
    } catch (error) {
      setState(prev => ({ ...prev, isMigrating: false }));
      message.error('配置迁移失败: ' + error);
    }
  };

  // 跳过迁移，继续使用本地存储
  const skipMigration = () => {
    configManager.forceUseLocalStorage();
    setState(prev => ({ 
      ...prev, 
      showMigrationModal: false,
      hasLocalConfigs: true 
    }));
    message.info('已切换到本地存储模式');
  };

  // 关闭迁移弹窗
  const closeMigrationModal = () => {
    setState(prev => ({ ...prev, showMigrationModal: false }));
  };

  // 手动触发检查迁移
  const checkMigration = () => {
    const hasLocal = configManager.hasLocalConfigs();
    if (hasLocal && configManager.getCurrentStorageMode() === 'server') {
      setState(prev => ({ 
        ...prev, 
        hasLocalConfigs: true,
        showMigrationModal: true 
      }));
    } else {
      message.info('没有发现需要迁移的本地配置');
    }
  };

  // 重新启用服务端存储
  const enableServerStorage = () => {
    configManager.enableServerStorage();
    message.success('已重新启用服务端存储');
    
    // 重新检查是否需要迁移
    const hasLocal = configManager.hasLocalConfigs();
    setState(prev => ({ 
      ...prev, 
      hasLocalConfigs: hasLocal,
      showMigrationModal: hasLocal
    }));
  };

  // 获取当前存储模式
  const getCurrentStorageMode = () => {
    return configManager.getCurrentStorageMode();
  };

  // 导出配置（用于备份）
  const exportConfigs = async () => {
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

  return {
    // 状态
    hasLocalConfigs: state.hasLocalConfigs,
    isMigrating: state.isMigrating,
    migrationResult: state.migrationResult,
    showMigrationModal: state.showMigrationModal,
    
    // 操作方法
    performMigration,
    skipMigration,
    closeMigrationModal,
    checkMigration,
    enableServerStorage,
    exportConfigs,
    getCurrentStorageMode,
    
    // 迁移确认弹窗 JSX
    MigrationModal: () => (
      <Modal
        title="发现本地配置"
        open={state.showMigrationModal}
        onOk={performMigration}
        onCancel={closeMigrationModal}
        okText="同步到服务端"
        cancelText="继续使用本地存储"
        confirmLoading={state.isMigrating}
        width={500}
        footer={[
          <button
            key="local"
            onClick={skipMigration}
            style={{
              marginRight: 8,
              padding: '4px 15px',
              border: '1px solid #d9d9d9',
              borderRadius: '6px',
              background: '#fff',
              cursor: 'pointer'
            }}
          >
            继续使用本地存储
          </button>,
          <button
            key="sync"
            onClick={performMigration}
            disabled={state.isMigrating}
            style={{
              padding: '4px 15px',
              border: 'none',
              borderRadius: '6px',
              background: '#1890ff',
              color: '#fff',
              cursor: state.isMigrating ? 'not-allowed' : 'pointer',
              opacity: state.isMigrating ? 0.6 : 1
            }}
          >
            {state.isMigrating ? '同步中...' : '同步到服务端'}
          </button>
        ]}
      >
        <div>
          <p>🔍 检测到您有本地存储的大模型和RAG配置。</p>
          <p>📤 <strong>同步到服务端</strong>：配置将保存到云端，不会因为清理浏览器缓存而丢失。</p>
          <p>💾 <strong>继续使用本地存储</strong>：配置仍保存在浏览器中，清理缓存时会丢失。</p>
          <p style={{ marginTop: 16, padding: 8, background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 4 }}>
            💡 建议选择"同步到服务端"以获得更好的数据安全性。
          </p>
        </div>
      </Modal>
    )
  };
}

export default useConfigMigration;
