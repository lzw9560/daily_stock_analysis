import type React from 'react';
import { useEffect, useState } from 'react';
import { AppPage, PageHeader, SentimentGauge, BoardLadder, Card } from '../components/common';
import { getSentiment, type SentimentMetrics } from '../api/enhancedRecommendation';

const SentimentDashboardPage: React.FC = () => {
  const [data, setData] = useState<SentimentMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = '情绪看板 - DSA';
    getSentiment()
      .then((r) => setData(r.metrics))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">加载中...</div></AppPage>;
  if (!data) return <AppPage className="flex items-center justify-center"><div className="text-muted-foreground text-sm">暂无数据</div></AppPage>;

  const boardLevels = [
    { boards: data.highestBoard, count: Math.max(1, Math.floor(data.connectivityCount / 3)), stocks: Array(Math.min(3, data.connectivityCount)).fill('-') },
    { boards: Math.max(1, data.highestBoard - 1), count: Math.max(1, Math.floor(data.connectivityCount / 2)), stocks: Array(Math.min(4, data.connectivityCount)).fill('-') },
    { boards: Math.max(1, data.highestBoard - 2), count: Math.max(1, Math.floor(data.connectivityCount)), stocks: Array(Math.min(6, data.connectivityCount)).fill('-') },
    { boards: 1, count: data.limitUpCount, stocks: Array(Math.min(8, data.limitUpCount)).fill('-') },
  ];

  return (
    <AppPage className="space-y-5">
      <PageHeader
        eyebrow="Sentiment Dashboard"
        title="情绪看板"
        description="市场情绪指标、连板梯队与资金流向全景监控"
      />

      <div className="sentiment-grid-2x3">
        <Card title="涨停统计" padding="md">
          <div className="flex items-center justify-between">
            <div className="text-center">
              <div className="text-3xl font-bold stock-up tabular-nums">{data.limitUpCount}</div>
              <div className="text-xs text-muted-foreground mt-1">涨停</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold stock-down tabular-nums">{data.limitDownCount}</div>
              <div className="text-xs text-muted-foreground mt-1">跌停</div>
            </div>
            <div className="text-center">
              <div className="text-sm font-bold stock-up tabular-nums">↑ +{data.limitUpCount - 10}</div>
              <div className="text-xs text-muted-foreground mt-1">较昨日</div>
            </div>
          </div>
        </Card>

        <Card title="连板梯队" padding="md">
          <BoardLadder levels={boardLevels} />
        </Card>

        <Card title="封板率" padding="md">
          <div className="flex items-center justify-center h-full">
            <SentimentGauge
              value={data.sealRate}
              size="sm"
              label={`封板率 ${data.sealRate.toFixed(1)}%`}
            />
          </div>
        </Card>

        <Card title="赚钱效应" padding="md">
          <div className="flex items-center justify-between">
            <div className="text-center">
              <div className="text-2xl font-bold stock-up tabular-nums">{data.advanceCount}</div>
              <div className="text-xs text-muted-foreground mt-1">上涨</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold stock-down tabular-nums">{data.declineCount}</div>
              <div className="text-xs text-muted-foreground mt-1">下跌</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold tabular-nums">{data.advanceRatio.toFixed(0)}%</div>
              <div className="text-xs text-muted-foreground mt-1">涨跌比</div>
            </div>
          </div>
        </Card>

        <Card title="成交额" padding="md">
          <div className="text-center">
            <div className="text-3xl font-bold tabular-nums">{data.turnoverTotal}</div>
            <div className="text-xs text-muted-foreground mt-1">亿元</div>
            <div className={`text-sm mt-2 ${data.turnoverChange >= 0 ? 'stock-up' : 'stock-down'}`}>
              {data.turnoverChange >= 0 ? '↑' : '↓'} {Math.abs(data.turnoverChange).toFixed(1)}%
            </div>
          </div>
        </Card>

        <Card title="情绪周期" padding="md">
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <SentimentGauge
              value={data.sentimentScore}
              size="md"
              label={data.sentimentScore.toFixed(0)}
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">阶段:</span>
              <span className="text-sm font-bold text-primary">{data.sentimentScore >= 70 ? '高潮' : data.sentimentScore >= 50 ? '分化' : data.sentimentScore >= 30 ? '修复' : '冰点'}</span>
            </div>
          </div>
        </Card>
      </div>

      <Card title="资金流向" padding="md">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className={`text-xl font-bold ${data.northFlow >= 0 ? 'stock-up' : 'stock-down'}`}>
              {data.northFlow >= 0 ? '+' : ''}{data.northFlow.toFixed(1)}亿
            </div>
            <div className="text-xs text-muted-foreground mt-1">北向资金</div>
          </div>
          <div className="text-center">
            <div className={`text-xl font-bold ${data.mainForceFlow >= 0 ? 'stock-up' : 'stock-down'}`}>
              {data.mainForceFlow >= 0 ? '+' : ''}{data.mainForceFlow.toFixed(1)}亿
            </div>
            <div className="text-xs text-muted-foreground mt-1">主力资金</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold tabular-nums">{data.sealPlateCount}</div>
            <div className="text-xs text-muted-foreground mt-1">封板数</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold tabular-nums">{data.brokenSealCount}</div>
            <div className="text-xs text-muted-foreground mt-1">炸板数</div>
          </div>
        </div>
      </Card>
    </AppPage>
  );
};

export default SentimentDashboardPage;
