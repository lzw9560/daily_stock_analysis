import { useCallback, useEffect, useRef, useState } from 'react';
import { Star, StarOff, RefreshCw, Check, Trash2, AlertCircle } from 'lucide-react';
import { motion } from 'motion/react';
import { sealPlateApi } from '../../api/sealPlate';
import { cn } from '../../utils/cn';

export type WatchlistButtonProps = {
  /** 股票代码 */
  code: string;
  /** 股票名称 */
  name: string;
  /** 评分（可选） */
  score?: number;
  /** 行业/板块（可选） */
  sector?: string | null;
  /** 来源标识，默认 "screening" */
  source?: string;
  /** 尺寸 */
  size?: 'sm' | 'md';
  /** 变体 */
  variant?: 'default' | 'iconOnly';
  /** 额外 class */
  className?: string;
  /** 状态变化回调 */
  onStateChange?: (inWatchlist: boolean) => void;
};

type FeedbackType = 'success' | 'remove' | 'error';

/**
 * 统一的"添加自选"按钮组件。
 *
 * 在挂载时通过 getWatchlistStatus 获取当前自选股代码集合，
 * 判断当前股票是否已在列表中，展示"添加自选"或"已关注"两种状态。
 *
 * 点击操作后会调用后端 API 并给出即时反馈提示，
 * 可用于选股结果、打板推荐、问股页等任何个股展示场景。
 */
export const WatchlistButton: React.FC<WatchlistButtonProps> = ({
  code,
  name,
  score = 0,
  sector = null,
  source = 'screening',
  size = 'sm',
  variant = 'default',
  className,
  onStateChange,
}) => {
  const [isInWatchlist, setIsInWatchlist] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [feedback, setFeedback] = useState<{ type: FeedbackType; message: string } | null>(null);
  const mountedRef = useRef(true);
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearFeedback = useCallback(() => {
    if (feedbackTimerRef.current) {
      clearTimeout(feedbackTimerRef.current);
      feedbackTimerRef.current = null;
    }
    setFeedback(null);
  }, []);

  const showFeedback = useCallback((type: FeedbackType, message: string) => {
    clearFeedback();
    setFeedback({ type, message });
    feedbackTimerRef.current = setTimeout(() => {
      setFeedback(null);
      feedbackTimerRef.current = null;
    }, 2200);
  }, [clearFeedback]);

  // 组件挂载时获取自选状态
  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const data = await sealPlateApi.getWatchlistStatus();
        if (!cancelled) {
          const inList = (data.codes || []).includes(code);
          setIsInWatchlist(inList);
          onStateChange?.(inList);
          setStatusLoaded(true);
        }
      } catch {
        if (!cancelled) {
          setStatusLoaded(true);
        }
      }
    };

    void fetchStatus();

    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
    // 仅 code 变化时重新获取
  }, [code, onStateChange]);

  // 清理定时器
  useEffect(() => {
    return () => {
      clearFeedback();
    };
  }, [clearFeedback]);

  const handleAdd = useCallback(async () => {
    setIsLoading(true);
    try {
      await sealPlateApi.addToWatchlist({
        code,
        name,
        score,
        sector,
        source,
      });
      setIsInWatchlist(true);
      onStateChange?.(true);
      showFeedback('success', `已添加 ${name} 到自选`);
    } catch (err) {
      const message = err instanceof Error ? err.message : '添加失败，请稍后重试';
      showFeedback('error', message);
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [code, name, score, sector, source, onStateChange, showFeedback]);

  const handleRemove = useCallback(async () => {
    setIsLoading(true);
    try {
      await sealPlateApi.removeFromWatchlist(code);
      setIsInWatchlist(false);
      onStateChange?.(false);
      showFeedback('remove', `已从自选移除 ${name}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : '移除失败，请稍后重试';
      showFeedback('error', message);
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [code, name, onStateChange, showFeedback]);

  // 在 status 加载完成之前不渲染，避免闪烁
  if (!statusLoaded) {
    return null;
  }

  if (isInWatchlist) {
    const label = variant === 'iconOnly' ? undefined : '已关注';
    return (
      <div className="relative inline-flex">
        <button
          type="button"
          onClick={handleRemove}
          disabled={isLoading}
          title="取消关注"
          className={cn(
            'inline-flex items-center gap-1 rounded-lg transition-colors disabled:opacity-50',
            size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm',
            'bg-amber-50 text-amber-700 hover:bg-red-50 hover:text-red-600 dark:bg-amber-900/20 dark:text-amber-400 dark:hover:bg-red-900/20 dark:hover:text-red-400',
            className,
          )}
        >
          {isLoading ? (
            <RefreshCw className={cn('animate-spin', size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
          ) : (
            <Star className={cn('fill-amber-500', size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
          )}
          {label}
        </button>
        {feedback ? (
            <motion.span
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              className={cn(
                'pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium shadow-lg',
                feedback.type === 'success' && 'bg-emerald-600 text-white',
                feedback.type === 'remove' && 'bg-slate-700 text-slate-100 dark:bg-slate-600',
                feedback.type === 'error' && 'bg-red-600 text-white',
              )}
            >
              <span className="inline-flex items-center gap-1">
                {feedback.type === 'success' && <Check className="h-3 w-3" />}
                {feedback.type === 'remove' && <Trash2 className="h-3 w-3" />}
                {feedback.type === 'error' && <AlertCircle className="h-3 w-3" />}
                {feedback.message}
              </span>
            </motion.span>
          ) : null}
      </div>
    );
  }

  const label = variant === 'iconOnly' ? undefined : '添加自选';
  return (
    <div className="relative inline-flex">
      <button
        type="button"
        onClick={handleAdd}
        disabled={isLoading}
        title="添加自选"
        className={cn(
          'inline-flex items-center gap-1 rounded-lg transition-colors disabled:opacity-50',
          size === 'sm' ? 'px-2 py-1 text-xs' : 'px-3 py-1.5 text-sm',
          'border border-border bg-surface text-secondary-text hover:border-amber-400 hover:text-amber-600 dark:hover:border-amber-500 dark:hover:text-amber-400',
          className,
        )}
      >
        {isLoading ? (
          <RefreshCw className={cn('animate-spin', size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
        ) : (
          <StarOff className={cn(size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
        )}
        {label}
      </button>
      {feedback ? (
        <motion.span
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          className={cn(
            'pointer-events-none absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium shadow-lg',
            feedback.type === 'success' && 'bg-emerald-600 text-white',
            feedback.type === 'error' && 'bg-red-600 text-white',
          )}
        >
          <span className="inline-flex items-center gap-1">
            {feedback.type === 'success' && <Check className="h-3 w-3" />}
            {feedback.type === 'error' && <AlertCircle className="h-3 w-3" />}
            {feedback.message}
          </span>
        </motion.span>
      ) : null}
    </div>
  );
};

export default WatchlistButton;
