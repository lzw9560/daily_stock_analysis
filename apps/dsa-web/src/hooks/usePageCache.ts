import { useEffect, useRef } from 'react';
import { useQueryClient, type QueryKey } from '@tanstack/react-query';
import { useCachedData, type UseCachedDataOptions } from './useCachedData';
import { useDataChangeSubscription } from './useDataChangeSubscription';
import { cacheEventBus } from '../lib/cacheEvents';

/**
 * usePageCache — 页面级缓存集成 Hook
 *
 * 一次调用同时享有以下能力：
 * 1. **数据缓存**：stale-while-revalidate 策略，先展示缓存再后台刷新
 * 2. **自动刷新**：定时 + 页面可见性变化时自动刷新
 * 3. **变更监听**：其他模块数据变更时自动静默刷新
 * 4. **后台无感**：刷新期间 isBackgroundRefreshing=true，不显示全局 loading
 *
 * 适用于推荐系统各子页面、仪表盘、交易页面等数据展示场景。
 *
 * @example
 * ```tsx
 * function MarketTrendPage() {
 *   const { data, isLoading, isBackgroundRefreshing } = usePageCache({
 *     queryKey: queryKeys.recommendation.marketTrend,
 *     queryFn: () => recommendationApi.getMarketTrend(),
 *     refetchInterval: 60000,
 *     listenKeys: [queryKeys.recommendation.all],
 *   });
 *
 *   // data 始终可用（缓存命中 or 新数据），即使是后台刷新
 *   return <MarketChart data={data} refreshing={isBackgroundRefreshing} />;
 * }
 * ```
 */
export interface UsePageCacheOptions<TData>
  extends Omit<UseCachedDataOptions<TData>, 'queryKey' | 'queryFn'> {
  queryKey: QueryKey;
  queryFn: () => Promise<TData>;
  /** 监听的额外 key（用于接收其他模块的变更通知） */
  listenKeys?: readonly QueryKey[];
  /** 页面可见时立即刷新 */
  refreshOnVisible?: boolean;
  /** 显示名称（调试用） */
  debugName?: string;
}

export interface UsePageCacheResult<TData> {
  /** 数据（缓存 or 新数据） */
  data: TData | undefined;
  /** 是否首次加载中 */
  isLoading: boolean;
  /** 是否后台刷新中（旧数据仍可用） */
  isBackgroundRefreshing: boolean;
  /** 错误信息 */
  error: Error | null;
  /** 手动刷新 */
  refetch: () => void;
  /** 通知数据变更（其他订阅者会刷新） */
  notifyDataChanged: () => void;
}

export function usePageCache<TData>(
  options: UsePageCacheOptions<TData>,
): UsePageCacheResult<TData> {
  const {
    queryKey,
    queryFn,
    listenKeys,
    refreshOnVisible = true,
    debugName,
    ...restOptions
  } = options;

  const queryClient = useQueryClient();
  const mountedRef = useRef(true);

  // 核心缓存查询
  const { data, isLoading, isBackgroundRefreshing, error } =
    useCachedData<TData>({
      queryKey,
      queryFn,
      listenToCacheEvents: true,
      eventKeys: listenKeys,
      ...restOptions,
    });

  // 订阅数据变更（前端匹配的 callback 式监听）
  useDataChangeSubscription({
    subscriptions: [
      {
        queryKey,
        subKeys: listenKeys,
      },
    ],
  });

  // 标记挂载状态
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // 通知数据变更
  const notifyDataChanged = () => {
    cacheEventBus.notifyDataChanged({
      keys: [queryKey],
      source: debugName ?? 'usePageCache',
    });
  };

  return {
    data,
    isLoading,
    isBackgroundRefreshing,
    error,
    refetch: () => {
      queryClient.refetchQueries({ queryKey, type: 'active' });
    },
    notifyDataChanged,
  };
}

export default usePageCache;
