import { useEffect, useRef } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { cacheEventBus, type CacheEvent } from '../lib/cacheEvents';

/**
 * 数据变更订阅配置
 */
export interface DataChangeSubscription {
  /** 需要监听的 queryKey */
  queryKey: QueryKey;
  /** 子 key（更精确的监听匹配） */
  subKeys?: readonly QueryKey[];
}

export interface UseDataChangeSubscriptionOptions {
  /** 要监听的查询列表 */
  subscriptions: DataChangeSubscription[];
  /** 是否启用，默认 true */
  enabled?: boolean;
}

export interface UseDataChangeSubscriptionResult {
  /** 手动触发指定查询的失效 */
  invalidate: (queryKey: QueryKey) => void;
  /** 手动触发指定查询的静默刷新 */
  refetch: (queryKey: QueryKey) => void;
}

/**
 * useDataChangeSubscription — 数据变更自动响应
 *
 * 监听全局数据变更事件，当其他模块通过 cacheEventBus 发出
 * data_changed 或 cache_invalidate 事件时，自动刷新相关缓存。
 *
 * 核心价值：
 * - 用户操作触发的数据变更能立即反应到所有相关页面
 * - 支持前缀匹配的模糊失效（如 ['recommendation'] 匹配所有推荐子页）
 * - 静默刷新不中断用户交互
 *
 * @example
 * ```tsx
 * useDataChangeSubscription({
 *   subscriptions: [
 *     { queryKey: ['recommendation'] },
 *     { queryKey: ['portfolio', 'positions'] },
 *   ],
 * });
 * ```
 */
export function useDataChangeSubscription(
  options: UseDataChangeSubscriptionOptions,
): UseDataChangeSubscriptionResult {
  const { subscriptions, enabled = true } = options;
  const queryClient = useQueryClient();
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  /**
   * 检查事件 key 是否匹配订阅中的任意 key
   */
  const matchesAnySubscription = (
    eventKeys: readonly QueryKey[],
  ): QueryKey | null => {
    for (const sub of subscriptions) {
      const allKeys = [sub.queryKey, ...(sub.subKeys ?? [])];
      for (const matchKey of allKeys) {
        for (const eventKey of eventKeys) {
          if (
            matchKey.length <= eventKey.length &&
            matchKey.every((seg, i) => seg === eventKey[i])
          ) {
            return sub.queryKey;
          }
        }
      }
    }
    return null;
  };

  useEffect(() => {
    if (!enabled) return;

    const handleCacheEvent = (event: CacheEvent) => {
      if (!event.keys || event.keys.length === 0) return;
      if (!enabledRef.current) return;

      const matchedKey = matchesAnySubscription(event.keys);
      if (matchedKey) {
        // 静默刷新：使用 invalidate 再 refetch 确保数据是最新的
        // invalidateQueries 标记数据为过期但不清除
        // refetchQueries 触发实际请求
        queryClient.invalidateQueries({ queryKey: matchedKey }).then(() => {
          queryClient.refetchQueries({
            queryKey: matchedKey,
            type: 'active',
          });
        });
      }
    };

    const unsubChanged = cacheEventBus.on('data_changed', handleCacheEvent);
    const unsubInvalidate = cacheEventBus.on(
      'cache_invalidate',
      handleCacheEvent,
    );

    return () => {
      unsubChanged();
      unsubInvalidate();
    };
  }, [enabled, queryClient, subscriptions]);

  const invalidate = (queryKey: QueryKey) => {
    cacheEventBus.notifyDataChanged({
      keys: [queryKey],
      source: 'useDataChangeSubscription',
    });
  };

  const refetch = (queryKey: QueryKey) => {
    queryClient.refetchQueries({ queryKey, type: 'active' });
  };

  return { invalidate, refetch };
}

export default useDataChangeSubscription;
