import { useCallback, useEffect, useRef } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { cacheEventBus } from '../lib/cacheEvents';

/**
 * 后台刷新调度策略配置
 */
export interface BackgroundRefreshSchedule {
  /** 精确的 queryKey */
  queryKey: QueryKey;
  /** 刷新间隔（毫秒） */
  intervalMs: number;
  /** 是否在页面隐藏时也刷新（默认 false） */
  refreshWhenHidden?: boolean;
  /** 是否启用（默认 true） */
  enabled?: boolean;
}

/**
 * 批量后台刷新调度选项
 */
export interface UseBackgroundRefreshOptions {
  /** 要定时刷新的查询列表 */
  schedules: BackgroundRefreshSchedule[];
  /** 全局是否启用（默认 true），可用于暂停所有定时刷新 */
  enabled?: boolean;
}

export interface UseBackgroundRefreshResult {
  /** 立即手动刷新所有已注册的查询 */
  refreshAll: () => void;
  /** 刷新指定的查询 */
  refresh: (queryKey: QueryKey) => void;
  /** 正在进行的后台刷新计数 */
  pendingRefreshCount: number;
}

/**
 * useBackgroundRefresh — 集中式后台定时刷新调度器
 *
 * 功能：
 * 1. 统一管理多个查询的定时刷新策略
 * 2. 页面隐藏时自动暂停（可配置例外）
 * 3. 窗口变为可见时立即补刷新
 * 4. 提供手动触发全部/单个刷新的能力
 *
 * @example
 * ```tsx
 * useBackgroundRefresh({
 *   schedules: [
 *     { queryKey: ['recommendation', 'market-trend'], intervalMs: 30000 },
 *     { queryKey: ['portfolio', 'positions'], intervalMs: 15000 },
 *   ],
 * });
 * ```
 */
export function useBackgroundRefresh(
  options: UseBackgroundRefreshOptions,
): UseBackgroundRefreshResult {
  const { schedules, enabled = true } = options;
  const queryClient = useQueryClient();
  const pendingRef = useRef(0);
  const intervalIdsRef = useRef<ReturnType<typeof setInterval>[]>([]);

  /** 刷新单个 query，不触发 loading 状态变化 */
  const refresh = useCallback(
    (queryKey: QueryKey) => {
      queryClient.refetchQueries({
        queryKey,
        type: 'active',
      });
    },
    [queryClient],
  );

  /** 刷新所有已注册的 query */
  const refreshAll = useCallback(() => {
    cacheEventBus.emit({
      type: 'background_refresh_start',
      timestamp: Date.now(),
      source: 'useBackgroundRefresh',
    });

    schedules.forEach((schedule) => {
      refresh(schedule.queryKey);
    });

    cacheEventBus.emit({
      type: 'background_refresh_complete',
      timestamp: Date.now(),
      source: 'useBackgroundRefresh',
    });
  }, [schedules, refresh]);

  /**
   * 页面可见性变化处理器
   * 从隐藏切换到可见时，立即刷新所有数据
   */
  useEffect(() => {
    if (!enabled) return;

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        // 立即补刷新所有数据
        refreshAll();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [enabled, refreshAll]);

  /**
   * 设置定时器
   */
  useEffect(() => {
    if (!enabled) {
      // 清除所有定时器
      intervalIdsRef.current.forEach(clearInterval);
      intervalIdsRef.current = [];
      return;
    }

    // 清除旧定时器
    intervalIdsRef.current.forEach(clearInterval);
    intervalIdsRef.current = [];

    const newIntervalIds: ReturnType<typeof setInterval>[] = [];

    schedules.forEach((schedule) => {
      if (schedule.enabled === false) return;

      const timer = setInterval(() => {
        // 默认仅在页面可见时刷新
        if (
          schedule.refreshWhenHidden ||
          document.visibilityState === 'visible'
        ) {
          refresh(schedule.queryKey);
        }
      }, schedule.intervalMs);

      newIntervalIds.push(timer);
    });

    intervalIdsRef.current = newIntervalIds;

    return () => {
      newIntervalIds.forEach(clearInterval);
    };
  }, [schedules, enabled, refresh]);

  return {
    refreshAll,
    refresh,
    pendingRefreshCount: pendingRef.current,
  };
}

export default useBackgroundRefresh;
