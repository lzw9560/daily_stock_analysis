import { useCachedData } from './useCachedData';
import type { QueryKey, UseQueryResult } from '@tanstack/react-query';

/**
 * 推荐系统数据加载 Hook — 基于 react-query 的缓存增强版
 *
 * 相比旧版 useRecommendationData 的改进：
 * 1. 自动缓存：相同 queryKey 的请求会复用缓存，避免重复请求
 * 2. SWR 策略：先展示缓存数据，后台自动刷新
 * 3. 事件响应：当其他模块通知数据变更时自动静默刷新
 * 4. 窗口聚焦：窗口重新获得焦点时自动检查更新
 * 5. 去重请求：同时多个组件请求相同数据只发一次网络请求
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, isBackgroundRefreshing } = useRecommendationData({
 *   queryKey: ['recommendation', 'market-trend'],
 *   queryFn: recommendationApi.getMarketTrend,
 * });
 * ```
 */
export interface UseRecommendationDataOptions<TData> {
  /** react-query 的 queryKey */
  queryKey: QueryKey;
  /** 数据获取函数 */
  queryFn: () => Promise<TData>;
  /** 后台自动刷新间隔（毫秒） */
  refetchInterval?: number;
  /** 数据新鲜期（毫秒），新鲜期内直接使用缓存 */
  staleTime?: number;
  /** 是否启用 */
  enabled?: boolean;
}

export type UseRecommendationDataResult<TData> = UseQueryResult<TData, Error> & {
  /** 是否正在进行后台静默刷新 */
  isBackgroundRefreshing: boolean;
  /** 手动触发后台刷新 */
  backgroundRefetch: () => void;
  /** 通知其他模块数据已变更 */
  notifyDataChanged: (source?: string) => void;
};

export function useRecommendationData<TData>(
  options: UseRecommendationDataOptions<TData>,
): UseRecommendationDataResult<TData> {
  const { queryKey, queryFn, refetchInterval, staleTime, enabled } = options;

  return useCachedData<TData>({
    queryKey,
    queryFn,
    refetchInterval,
    staleTime,
    enabled,
    listenToCacheEvents: true,
  });
}

export default useRecommendationData;
