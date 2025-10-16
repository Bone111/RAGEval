# ConfigStorageIndicator 组件

显示配置存储状态（云端/本地）的指示器组件，提供配置迁移和管理功能。

## 功能特性

- 🔍 实时显示当前配置存储模式（云端/本地）
- 🔄 一键配置迁移功能  
- 📤 配置导出备份功能
- 🔌 自动重试云端连接
- 📱 响应式设计

## 使用方法

### 基础用法

```tsx
import ConfigStorageIndicator from '@/components/ConfigStorageIndicator';

function SettingsPage() {
  return (
    <div>
      <h1>系统设置</h1>
      
      {/* 显示配置存储状态 */}
      <ConfigStorageIndicator />
      
      {/* 其他设置内容 */}
    </div>
  );
}
```

### 自定义样式

```tsx
import ConfigStorageIndicator from '@/components/ConfigStorageIndicator';

function MyComponent() {
  return (
    <ConfigStorageIndicator 
      className="my-custom-style"
      showActions={false}  // 隐藏操作按钮
    />
  );
}
```

### 在布局中使用

```tsx
// 在顶部导航栏中显示
function TopNavbar() {
  return (
    <div className="navbar">
      <div className="navbar-left">
        <Logo />
        <Navigation />
      </div>
      
      <div className="navbar-right">
        <ConfigStorageIndicator showActions={true} />
        <UserMenu />
      </div>
    </div>
  );
}
```

### 在设置页面中使用

```tsx
// 在设置页面中提供完整功能
function ConfigurationPage() {
  return (
    <div className="config-page">
      <div className="config-header">
        <h2>配置管理</h2>
        <ConfigStorageIndicator />
      </div>
      
      <div className="config-content">
        {/* 模型配置 */}
        <ModelConfigSection />
        
        {/* RAG配置 */}
        <RAGConfigSection />
      </div>
    </div>
  );
}
```

## Props

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| className | string | '' | 自定义 CSS 类名 |
| showActions | boolean | true | 是否显示操作按钮（迁移、导出等） |

## 状态说明

### 云端存储 🟢
- 配置保存在服务器数据库中
- 不会因浏览器缓存清理而丢失
- 支持跨设备同步

### 本地存储 🟡  
- 配置保存在浏览器 localStorage 中
- 清理缓存时会丢失
- 建议迁移到云端存储

## 操作按钮

### 切换云端
- 当前为本地存储模式时显示
- 尝试重新连接服务端存储
- 连接成功后会自动切换模式

### 迁移配置
- 将本地配置上传到服务端
- 支持批量迁移
- 显示详细的迁移结果

### 导出配置
- 将所有配置导出为 JSON 文件
- 可用于备份和迁移
- 支持模型配置和 RAG 配置

## 自动功能

### 迁移提示
- 自动检测本地配置
- 显示迁移确认弹窗
- 用户可选择迁移或继续使用本地存储

### 降级处理
- 服务端不可用时自动降级
- 无缝切换到本地存储
- 避免功能中断

### 状态同步
- 定期检查存储模式状态
- 实时更新指示器显示
- 确保信息准确性

## 样式定制

```css
/* 自定义容器样式 */
.my-custom-indicator {
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border: none;
  color: white;
}

/* 自定义按钮样式 */
.my-custom-indicator .ant-btn-link {
  color: rgba(255, 255, 255, 0.85);
}

.my-custom-indicator .ant-btn-link:hover {
  color: white;
  background: rgba(255, 255, 255, 0.1);
}
```

## 事件处理

组件内部自动处理所有用户交互：

- ✅ 状态切换
- ✅ 配置迁移  
- ✅ 错误处理
- ✅ 用户反馈

无需手动绑定事件处理器。

## 最佳实践

1. **导航栏使用**: 在顶部导航栏显示，让用户随时了解配置状态
2. **设置页面**: 在配置管理页面提供完整功能
3. **隐藏操作**: 在只需要显示状态的地方设置 `showActions={false}`
4. **响应式**: 组件已支持移动端响应式设计

## 注意事项

- 需要用户登录后才能正常工作
- 依赖 `useConfigMigration` hooks
- 需要后端 API 支持
- 建议在应用加载时预先检查配置状态
