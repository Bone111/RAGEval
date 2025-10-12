/**
 * 共享任务轮询Hook
 * 统一管理任务状态更新，避免多个页面重复轮询
 */
import { useEffect, useRef, useCallback } from 'react';
import { evalscopeService } from '../services/evalscope.service';
import type { EvalTask, EvalTaskDetail } from '../types/evalscope.types';

interface TaskUpdateCallback {
  (task: EvalTask | EvalTaskDetail): void;
}

interface SharedTaskPollingOptions {
  // 轮询间隔（毫秒）
  interval?: number;
  // 是否启用轮询
  enabled?: boolean;
  // 任务状态变化时的回调
  onTaskUpdate?: TaskUpdateCallback;
}

class SharedTaskPollingManager {
  private static instance: SharedTaskPollingManager;
  private pollingInterval: NodeJS.Timeout | null = null;
  private subscribers: Map<number, TaskUpdateCallback[]> = new Map();
  private taskCache: Map<number, { task: EvalTask | EvalTaskDetail; timestamp: number }> = new Map();
  private isPolling = false;
  private readonly CACHE_TTL = 5000; // 缓存5秒

  static getInstance(): SharedTaskPollingManager {
    if (!SharedTaskPollingManager.instance) {
      SharedTaskPollingManager.instance = new SharedTaskPollingManager();
    }
    return SharedTaskPollingManager.instance;
  }

  /**
   * 订阅任务更新
   */
  subscribe(taskId: number, callback: TaskUpdateCallback): () => void {
    if (!this.subscribers.has(taskId)) {
      this.subscribers.set(taskId, []);
    }
    this.subscribers.get(taskId)!.push(callback);

    // 立即返回缓存的任务数据（如果存在）
    const cached = this.taskCache.get(taskId);
    if (cached && Date.now() - cached.timestamp < this.CACHE_TTL) {
      callback(cached.task);
    }

    // 启动轮询（如果还没有启动）
    this.startPolling();

    // 返回取消订阅函数
    return () => {
      this.unsubscribe(taskId, callback);
    };
  }

  /**
   * 取消订阅任务更新
   */
  unsubscribe(taskId: number, callback: TaskUpdateCallback): void {
    const callbacks = this.subscribers.get(taskId);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
      
      // 如果没有订阅者了，移除该任务
      if (callbacks.length === 0) {
        this.subscribers.delete(taskId);
        this.taskCache.delete(taskId);
      }
    }

    // 如果没有订阅者了，停止轮询
    if (this.subscribers.size === 0) {
      this.stopPolling();
    }
  }

  /**
   * 启动轮询
   */
  private startPolling(): void {
    if (this.isPolling) return;

    this.isPolling = true;
    this.pollingInterval = setInterval(() => {
      this.pollTasks();
    }, 3000); // 3秒轮询一次
  }

  /**
   * 停止轮询
   */
  private stopPolling(): void {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
    this.isPolling = false;
  }

  /**
   * 轮询所有订阅的任务
   */
  private async pollTasks(): Promise<void> {
    const taskIds = Array.from(this.subscribers.keys());
    if (taskIds.length === 0) return;

    try {
      // 并行获取所有任务的最新状态
      const tasks = await Promise.all(
        taskIds.map(async (taskId) => {
          try {
            const task = await evalscopeService.getTask(taskId);
            return { taskId, task };
          } catch (error) {
            console.warn(`获取任务 ${taskId} 失败:`, error);
            return null;
          }
        })
      );

      // 更新缓存并通知订阅者
      tasks.forEach((result) => {
        if (result) {
          const { taskId, task } = result;
          
          // 更新缓存
          this.taskCache.set(taskId, {
            task,
            timestamp: Date.now()
          });

          // 通知所有订阅者
          const callbacks = this.subscribers.get(taskId);
          if (callbacks) {
            callbacks.forEach(callback => {
              try {
                callback(task);
              } catch (error) {
                console.error(`任务 ${taskId} 更新回调执行失败:`, error);
              }
            });
          }
        }
      });
    } catch (error) {
      console.error('轮询任务失败:', error);
    }
  }

  /**
   * 手动刷新指定任务
   */
  async refreshTask(taskId: number): Promise<EvalTask | EvalTaskDetail | null> {
    try {
      const task = await evalscopeService.getTask(taskId);
      
      // 更新缓存
      this.taskCache.set(taskId, {
        task,
        timestamp: Date.now()
      });

      // 通知订阅者
      const callbacks = this.subscribers.get(taskId);
      if (callbacks) {
        callbacks.forEach(callback => {
          try {
            callback(task);
          } catch (error) {
            console.error(`任务 ${taskId} 手动刷新回调执行失败:`, error);
          }
        });
      }

      return task;
    } catch (error) {
      console.error(`手动刷新任务 ${taskId} 失败:`, error);
      return null;
    }
  }

  /**
   * 获取当前订阅的任务数量
   */
  getSubscribedTaskCount(): number {
    return this.subscribers.size;
  }

  /**
   * 获取当前轮询状态
   */
  isPollingActive(): boolean {
    return this.isPolling;
  }
}

/**
 * 共享任务轮询Hook
 */
export function useSharedTaskPolling(
  taskId: number,
  options: SharedTaskPollingOptions = {}
) {
  const {
    interval = 3000,
    enabled = true,
    onTaskUpdate
  } = options;

  const managerRef = useRef<SharedTaskPollingManager>();
  const callbackRef = useRef<TaskUpdateCallback>();
  const unsubscribeRef = useRef<(() => void) | null>(null);

  // 初始化管理器
  if (!managerRef.current) {
    managerRef.current = SharedTaskPollingManager.getInstance();
  }

  // 更新回调引用
  callbackRef.current = onTaskUpdate;

  // 订阅任务更新
  useEffect(() => {
    if (!enabled || !taskId) return;

    const manager = managerRef.current!;
    
    const unsubscribe = manager.subscribe(taskId, (task) => {
      if (callbackRef.current) {
        callbackRef.current(task);
      }
    });

    unsubscribeRef.current = unsubscribe;

    return unsubscribe;
  }, [taskId, enabled]);

  // 手动刷新任务
  const refreshTask = useCallback(async () => {
    if (!taskId) return null;
    return await managerRef.current!.refreshTask(taskId);
  }, [taskId]);

  // 获取unsubscribe函数
  const getUnsubscribe = useCallback(() => {
    return unsubscribeRef.current;
  }, []);

  return {
    refreshTask,
    getUnsubscribe,
    isPollingActive: managerRef.current?.isPollingActive() || false,
    subscribedTaskCount: managerRef.current?.getSubscribedTaskCount() || 0
  };
}

export default SharedTaskPollingManager;
