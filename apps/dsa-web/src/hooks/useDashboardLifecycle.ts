import { useEffect, useRef, useCallback } from 'react';
import type { TaskInfo } from '../types/analysis';
import { useTaskStream } from './useTaskStream';
import { cacheEventBus } from '../lib/cacheEvents';

type UseDashboardLifecycleOptions = {
  loadInitialHistory: () => Promise<void>;
  refreshHistory: (silent?: boolean) => Promise<void>;
  refreshActiveTasks: () => Promise<void>;
  syncTaskCreated: (task: TaskInfo) => void;
  syncTaskUpdated: (task: TaskInfo) => void;
  syncTaskFailed: (task: TaskInfo) => void;
  removeTask: (taskId: string) => void;
  enabled?: boolean;
};

/**
 * 首页生命周期 Hook — 缓存感知版
 *
 * 增强功能：
 * 1. 任务完成/失败时自动通知缓存事件总线，触发相关页面静默刷新
 * 2. 页面可见性变化时利用缓存策略（而非简单重新请求）
 * 3. 任务创建/更新时通过 SSE 实时同步，而非高频轮询
 */
export function useDashboardLifecycle({
  loadInitialHistory,
  refreshHistory,
  refreshActiveTasks,
  syncTaskCreated,
  syncTaskUpdated,
  syncTaskFailed,
  removeTask,
  enabled = true,
}: UseDashboardLifecycleOptions): void {
  const removalTimeoutsRef = useRef<number[]>([]);
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  // 初始加载
  useEffect(() => {
    if (!enabled) return;
    void loadInitialHistory();
    void refreshActiveTasks();
  }, [enabled, loadInitialHistory, refreshActiveTasks]);

  // 定时轮询（30 秒），作为 SSE 的降级后备
  useEffect(() => {
    if (!enabled) return;

    const intervalId = window.setInterval(() => {
      if (enabledRef.current) {
        void refreshHistory(true);
        void refreshActiveTasks();
      }
    }, 30_000);

    return () => window.clearInterval(intervalId);
  }, [enabled, refreshHistory, refreshActiveTasks]);

  // 页面可见性变化：可见时静默刷新
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (
        document.visibilityState === 'visible' &&
        enabledRef.current
      ) {
        void refreshHistory(true);
        void refreshActiveTasks();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [enabled, refreshHistory, refreshActiveTasks]);

  // 清理
  useEffect(() => {
    return () => {
      removalTimeoutsRef.current.forEach((timeoutId) =>
        window.clearTimeout(timeoutId),
      );
      removalTimeoutsRef.current = [];
    };
  }, []);

  // 计划延迟移除任务
  const scheduleTaskRemoval = useCallback(
    (taskId: string, delayMs: number) => {
      const timeoutId = window.setTimeout(() => {
        removeTask(taskId);
        removalTimeoutsRef.current = removalTimeoutsRef.current.filter(
          (item) => item !== timeoutId,
        );
      }, delayMs);

      removalTimeoutsRef.current.push(timeoutId);
    },
    [removeTask],
  );

  // SSE 任务流 + 缓存事件通知
  useTaskStream({
    onTaskCreated: syncTaskCreated,
    onTaskStarted: syncTaskUpdated,
    onTaskProgress: syncTaskUpdated,
    onConnected: () => {
      void refreshActiveTasks();
    },
    onTaskCompleted: (task) => {
      syncTaskUpdated(task);
      void refreshHistory(true);

      // 🔔 通知缓存系统：分析任务完成，相关数据已变更
      cacheEventBus.notifyDataChanged({
        keys: [
          ['analysis'],
          ['recommendation'],
          ['history'],
          ['stocks', task.stockCode],
        ],
        source: 'dashboard-lifecycle',
        meta: {
          taskId: task.taskId,
          stockCode: task.stockCode,
          stockName: task.stockName,
        },
      });

      scheduleTaskRemoval(task.taskId, 2_000);
    },
    onTaskFailed: (task) => {
      syncTaskFailed(task);
      scheduleTaskRemoval(task.taskId, 5_000);
    },
    onError: () => {
      console.warn('SSE connection disconnected, reconnecting...');
    },
    enabled,
  });
}

export default useDashboardLifecycle;
