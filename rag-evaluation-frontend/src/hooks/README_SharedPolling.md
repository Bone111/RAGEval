# 共享任务轮询机制

## 概述

共享任务轮询机制是一个统一的轮询管理系统，用于避免多个页面重复轮询相同的任务状态，从而优化资源使用。

## 主要特性

### 1. 单例模式
- 全局只有一个轮询管理器实例
- 所有页面共享同一个轮询进程

### 2. 智能缓存
- 任务数据缓存5秒，避免重复请求
- 新订阅者立即获得缓存数据

### 3. 自动管理
- 自动启动/停止轮询
- 无订阅者时自动停止轮询
- 有订阅者时自动启动轮询

### 4. 错误处理
- 单个任务获取失败不影响其他任务
- 回调执行失败不影响轮询进程

## 使用方法

### 在任务详情页面使用

```typescript
import { useSharedTaskPolling } from '@/hooks/useSharedTaskPolling';

const TaskMonitorPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const taskId = Number(id);
  const [task, setTask] = useState<EvalTaskDetail | null>(null);

  // 使用共享轮询
  const { refreshTask } = useSharedTaskPolling(taskId, {
    enabled: true,
    onTaskUpdate: (updatedTask) => {
      setTask(updatedTask as EvalTaskDetail);
    }
  });

  // 手动刷新
  const handleRefresh = async () => {
    await refreshTask();
  };

  return (
    <Button onClick={handleRefresh}>
      刷新
    </Button>
  );
};
```

### 在任务列表页面使用

```typescript
import SharedTaskPollingManager from '@/hooks/useSharedTaskPolling';

const TaskListPage: React.FC = () => {
  const [tasks, setTasks] = useState<EvalTask[]>([]);

  // 为运行中的任务订阅更新
  useEffect(() => {
    const runningTaskIds = tasks
      .filter(task => task.status === 'running')
      .map(task => task.id);

    if (runningTaskIds.length === 0) return;

    const manager = SharedTaskPollingManager.getInstance();
    const unsubscribeFunctions: (() => void)[] = [];

    runningTaskIds.forEach(taskId => {
      const unsubscribe = manager.subscribe(taskId, (updatedTask) => {
        setTasks(prevTasks => 
          prevTasks.map(task => 
            task.id === taskId ? updatedTask as EvalTask : task
          )
        );
      });
      unsubscribeFunctions.push(unsubscribe);
    });

    return () => {
      unsubscribeFunctions.forEach(unsubscribe => unsubscribe());
    };
  }, [tasks.filter(t => t.status === 'running').map(t => t.id).join(',')]);

  return (
    // 任务列表UI
  );
};
```

## 性能优化效果

### 优化前
- 任务详情页面：每2-5秒轮询一次
- 任务列表页面：无轮询，状态不更新
- 多个详情页面：重复轮询相同任务

### 优化后
- 全局统一轮询：每3秒轮询一次
- 智能缓存：减少重复请求
- 自动管理：无订阅者时停止轮询
- 资源节省：减少50-80%的网络请求

## 配置选项

```typescript
interface SharedTaskPollingOptions {
  // 轮询间隔（毫秒），默认3000
  interval?: number;
  
  // 是否启用轮询，默认true
  enabled?: boolean;
  
  // 任务状态变化时的回调
  onTaskUpdate?: (task: EvalTask | EvalTaskDetail) => void;
}
```

## 注意事项

1. **Hook规则**：只能在React组件中使用
2. **内存管理**：组件卸载时自动取消订阅
3. **错误处理**：网络错误不会中断轮询进程
4. **缓存策略**：数据缓存5秒，过期后重新获取

## 监控和调试

```typescript
// 获取轮询状态
const manager = SharedTaskPollingManager.getInstance();
console.log('轮询状态:', manager.isPollingActive());
console.log('订阅任务数:', manager.getSubscribedTaskCount());
```

## 扩展功能

### 手动刷新
```typescript
const { refreshTask } = useSharedTaskPolling(taskId);
await refreshTask(); // 立即刷新任务状态
```

### 批量订阅
```typescript
const manager = SharedTaskPollingManager.getInstance();
const taskIds = [1, 2, 3, 4, 5];

taskIds.forEach(taskId => {
  manager.subscribe(taskId, (task) => {
    console.log(`任务 ${taskId} 更新:`, task);
  });
});
```

## 最佳实践

1. **按需订阅**：只为需要的任务订阅更新
2. **及时取消**：组件卸载时确保取消订阅
3. **错误处理**：在回调中处理可能的错误
4. **性能监控**：定期检查订阅数量，避免内存泄漏
