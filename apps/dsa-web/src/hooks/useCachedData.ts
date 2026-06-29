import { useCallback, useEffect, useRef } from 'react';
import {
  useQuery,
  useQueryClient,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from '@tanstack/react-query';
import { cacheEventBus, type CacheEvent } from '../lib/cacheEvents';

/**
 * useCachedData — 带缓存策略的通用数据获取 Hook
 *
 * 相比原生 react-query 的增强功能：
 * 1. **Stale-While-Revalidate (SWR)**：先展示缓存数据，后台静默刷新
 * 2. **缓存事件订阅**：自动响应 data_changed 事件，后台刷新
 * 3. **定时后台刷新**：可配置的自动刷新间隔
 * 4. **可见性感知**：页面隐藏时暂停刷新，显示时立即补刷新
 * 5. **无缝更新**：刷新期间不显示 loading，保持旧数据可用直到新数据到达
 *
 * @example
 * ```tsx
 * const { data, isLoading, isBackgroundRefreshing } = useCachedData({
 *   queryKey: ['recommendation', 'market-trend'],
 *   queryFn: () => recommendationApi.getMarketTrend(),
 *   refetchInterval: 60000,
 *   staleTime: 30000,
 * });
 * ```
 */
export interface UseCachedDataOptions<TData, TError = Error>
  extends Omit<
    UseQueryOptions<TData, TError, TData, QueryKey>,
    'queryKey' | 'queryFn'
  > {
  /** react-query 的 queryKey，同时用作缓存事件匹配 key */
  queryKey: QueryKey;
  /** 数据获取函数 */
  queryFn: () => Promise<TData>;
  /** 后台自动刷新间隔（毫秒），默认不开启 */
  refetchInterval?: number;
  /**
   * 是否启用缓存事件监听，当其他模块通知数据变更时自动刷新
   * @default true
   */
  listenToCacheEvents?: boolean;
  /**
   * 额外的缓存事件匹配 key 列表
   * 当收到 data_changed 事件时，若事件的 keys 中包含这些 key，则触发刷新
   */
  eventKeys?: readonly QueryKey[];
}

export type UseCachedDataResult<TData, TError = Error> = UseQueryResult<TData, TError> & {
  /** 是否正在进行后台静默刷新（此时旧数据仍可用） */
  isBackgroundRefreshing: boolean;
  /** 手动触发后台刷新 */
  backgroundRefetch: () => void;
  /** 通知其他模块数据已变更 */
  notifyDataChanged: (source?: string) => void;
};

export function useCachedData<TData, TError = Error>(
  options: UseCachedDataOptions<TData, TError>,
): UseCachedDataResult<TData, TError> {
  const {
    queryKey,
    queryFn,
    refetchInterval,
    listenToCacheEvents = true,
    eventKeys,
    ...restOptions
  } = options;

  const queryClient = useQueryClient();
  const isBackgroundRef = useRef(false);

  const queryResult = useQuery<TData, TError, TData, QueryKey>({
    queryKey,
    queryFn,
    ...restOptions,
  });

  const {
    isFetching,
    isStale,
    data,
    isLoading,
  } = queryResult;

  // 判断是否为后台刷新：数据已存在 且 正在获取中
  const isBackgroundRefreshing = !isLoading && isFetching && data !== undefined;

  // 更新 ref 用于回调闭包
  useEffect(() => {
    isBackgroundRef.current = isBackgroundRefreshing;
  }, [isBackgroundRefreshing]);

  /**
   * 手动后台刷新：使用 queryClient.refetchQueries 而非重新渲染
   * 在不改变组件状态的前提下触发静默刷新
   */
  const backgroundRefetch = useCallback(() => {
    queryClient.refetchQueries({
      queryKey,
      type: 'active',
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey]);

  /**
   * 通知事件总线：数据已变更，其他订阅者应刷新
   */
  const notifyDataChanged = useCallback(
    (source?: string) => {
      cacheEventBus.notifyDataChanged({
        keys: [queryKey],
        source: source ?? 'useCachedData',
      });
    },
    [queryKey],
  );

  /**
   * 订阅缓存事件
   * 当收到 data_changed/cache_invalidate 事件时，若 key 匹配则静默刷新
   */
  useEffect(() => {
    if (!listenToCacheEvents) return;

    const keysToMatch = [queryKey, ...(eventKeys ?? [])];

    const handleDataChanged = (event: CacheEvent) => {
      if (!event.keys || event.keys.length === 0) return;

      const shouldRefresh = event.keys.some((eventKey) =>
        keysToMatch.some(
          (matchKey) =>
            // 支持前缀匹配：['recommendation'] 匹配 ['recommendation', 'any-sub']
            matchKey.length <= eventKey.length &&
            matchKey.every((seg, i) => seg === eventKey[i]),
        ),
      );

      if (shouldRefresh) {
        // 静默后台刷新，不影响当前 UI
        backgroundRefetch();
      }
    };

    const unsubChanged = cacheEventBus.on('data_changed', handleDataChanged);
    const unsubInvalidate = cacheEventBus.on('cache_invalidate', handleDataChanged);

    return () => {
      unsubChanged();
      unsubInvalidate();
    };
  }, [queryKey, eventKeys, listenToCacheEvents, backgroundRefetch]);

  /**
   * 定时后台刷新
   */
  useEffect(() => {
    if (!refetchInterval || refetchInterval <= 0) return;

    const timer = setInterval(() => {
      if (document.visibilityState === 'visible') {
        backgroundRefetch();
      }
    }, refetchInterval);

    return () => clearInterval(timer);
  }, [refetchInterval, backgroundRefetch]);

  /**
   * 页面可见性变化时刷新
   * 当页面从隐藏变为可见时，若数据已过期则刷新
   */
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && isStale) {
        backgroundRefetch();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () =>
      document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [isStale, backgroundRefetch]);

  return {
    ...queryResult,
    isBackgroundRefreshing,
    backgroundRefetch,
    notifyDataChanged,
  };
}

export default useCachedData;
