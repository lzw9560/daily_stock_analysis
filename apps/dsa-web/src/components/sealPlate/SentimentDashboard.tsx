import { useState, useEffect, useCallback } from 'react';
import { Brain, TrendingUp, TrendingDown, Minus, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { SentimentAnalysis } from '@/types/sealPlate';

interface Props {
  onPositionChange?: (position: number) => void;
}

export default function SentimentDashboard({ onPositionChange }: Props) {
  const [sentiment, setSentiment] = useState<SentimentAnalysis | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchSentiment = useCallback(async () => {
    try {
      const data = await sealPlateApi.getSentiment();
      setSentiment(data);
      if (onPositionChange) {
        onPositionChange(data.suggestedPosition);
      }
    } catch (error) {
      console.error('获取情绪数据失败:', error);
    } finally {
      setLoading(false);
    }
  }, [onPositionChange]);

  useEffect(() => {
    fetchSentiment();
  }, [fetchSentiment]);

  const getPhaseIcon = (phase: string) => {
    switch (phase) {
      case '冰点期':
        return <Minus className="w-6 h-6 text-blue-500" />;
      case '启动期':
        return <TrendingUp className="w-6 h-6 text-green-500" />;
      case '发酵期':
        return <TrendingUp className="w-6 h-6 text-emerald-500" />;
      case '高潮期':
        return <AlertTriangle className="w-6 h-6 text-orange-500" />;
      case '退潮期':
        return <TrendingDown className="w-6 h-6 text-red-500" />;
      default:
        return <Brain className="w-6 h-6 text-gray-500" />;
    }
  };

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case '冰点期':
        return 'bg-blue-500/10 border-blue-500/30';
      case '启动期':
        return 'bg-green-500/10 border-green-500/30';
      case '发酵期':
        return 'bg-emerald-500/10 border-emerald-500/30';
      case '高潮期':
        return 'bg-orange-500/10 border-orange-500/30';
      case '退潮期':
        return 'bg-red-500/10 border-red-500/30';
      default:
        return 'bg-gray-500/10 border-gray-500/30';
    }
  };

  const getSentimentColor = (index: number) => {
    if (index >= 70) return 'text-red-500';
    if (index >= 50) return 'text-orange-500';
    if (index >= 30) return 'text-yellow-500';
    return 'text-blue-500';
  };

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载情绪数据..." />
        </div>
      </Card>
    );
  }

  if (!sentiment) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <p className="text-muted-foreground">暂无情绪数据</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className={getPhaseColor(sentiment.phase)}>
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-5 h-5" />
        <span className="font-medium">情绪周期仪表盘</span>
      </div>
      <div className="space-y-4">
        {/* 情绪指数显示 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getPhaseIcon(sentiment.phase)}
            <div>
              <p className="text-sm text-muted-foreground">当前阶段</p>
              <p className="text-lg font-semibold">{sentiment.phaseLabel}</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">情绪指数</p>
            <p className={`text-3xl font-bold ${getSentimentColor(sentiment.sentimentIndex)}`}>
              {sentiment.sentimentIndex}
            </p>
          </div>
        </div>

        {/* 情绪进度条 */}
        <div className="relative h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className="absolute h-full bg-gradient-to-r from-blue-500 via-yellow-500 to-red-500 transition-all duration-500"
            style={{ width: `${sentiment.sentimentIndex}%` }}
          />
        </div>

        {/* 仓位建议 */}
        <div className="bg-background/50 rounded-lg p-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">建议仓位</span>
            <span className="text-lg font-bold text-primary">
              {sentiment.suggestedPosition}%
            </span>
          </div>
          <div className="text-xs text-muted-foreground">
            范围: {sentiment.positionRange}
          </div>
          <div className="relative h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className="absolute h-full bg-primary transition-all duration-500"
              style={{ width: `${sentiment.suggestedPosition}%` }}
            />
          </div>
        </div>

        {/* 策略建议 */}
        <div className="bg-background/50 rounded-lg p-3">
          <p className="text-sm font-medium mb-1">策略建议</p>
          <p className="text-sm text-muted-foreground">{sentiment.strategy}</p>
        </div>

        {/* 警告信息 */}
        {sentiment.warning && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-500 mt-0.5" />
            <p className="text-sm text-orange-600 dark:text-orange-400">
              {sentiment.warning}
            </p>
          </div>
        )}

        {/* 指标详情 */}
        {sentiment.indicators && Object.keys(sentiment.indicators).length > 0 && (
          <div className="grid grid-cols-2 gap-2 text-xs">
            {Object.entries(sentiment.indicators).map(([key, value]) => (
              <div key={key} className="flex justify-between bg-background/30 rounded px-2 py-1">
                <span className="text-muted-foreground">{key}</span>
                <span className="font-medium">{Math.round(value)}%</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
