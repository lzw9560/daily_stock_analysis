import { Clock, DollarSign, Users, BarChart2, TrendingUp, Activity, Calendar, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import type { SealPlateStockResponse } from '@/types/sealPlate';

interface Props {
  stock: SealPlateStockResponse;
  onClose?: () => void;
}

interface ScoreItem {
  label: string;
  value: number;
  maxScore: number;
  icon: typeof Clock;
  description: string;
}

export default function SealScoreCard({ stock, onClose }: Props) {
  // 计算各项评分
  const getScoreItems = (): ScoreItem[] => {
    // 封板时间评分
    let timeScore = 50;
    let timeDesc = '未知';
    if (stock.sealTime) {
      const hour = parseInt(stock.sealTime.split('T')[1]?.split(':')[0] || '0');
      if (hour < 10) {
        timeScore = 90;
        timeDesc = '早盘封板';
      } else if (hour < 14) {
        timeScore = 70;
        timeDesc = '午盘封板';
      } else {
        timeScore = 40;
        timeDesc = '尾盘封板';
      }
    }

    // 封单金额评分
    let amountScore = 50;
    let amountDesc = '一般';
    if (stock.sealAmount >= 10000) {
      amountScore = 95;
      amountDesc = '封单充足';
    } else if (stock.sealAmount >= 5000) {
      amountScore = 80;
      amountDesc = '封单较大';
    } else if (stock.sealAmount >= 1000) {
      amountScore = 60;
      amountDesc = '封单一般';
    } else {
      amountScore = 30;
      amountDesc = '封单较小';
    }

    return [
      {
        label: '涨停时间',
        value: timeScore,
        maxScore: 20,
        icon: Clock,
        description: timeDesc,
      },
      {
        label: '封单金额',
        value: amountScore,
        maxScore: 15,
        icon: DollarSign,
        description: amountDesc,
      },
      {
        label: '板块联动',
        value: stock.sector ? 80 : 40,
        maxScore: 15,
        icon: Users,
        description: stock.sector || '无板块效应',
      },
      {
        label: '换手率',
        value: stock.turnoverRate >= 5 && stock.turnoverRate <= 20 ? 90 : 50,
        maxScore: 15,
        icon: Activity,
        description: `${stock.turnoverRate.toFixed(1)}%`,
      },
      {
        label: '均线形态',
        value: 70,
        maxScore: 10,
        icon: TrendingUp,
        description: '多头排列',
      },
      {
        label: '连板高度',
        value: 50,
        maxScore: 5,
        icon: Calendar,
        description: '首板',
      },
    ];
  };

  const scoreItems = getScoreItems();
  const totalScore = Math.round(scoreItems.reduce((sum, item) => sum + (item.value / 100) * item.maxScore, 0));

  const getScoreLevel = (score: number) => {
    if (score >= 85) return { label: '极佳', color: 'bg-red-500', textColor: 'text-white' };
    if (score >= 70) return { label: '良好', color: 'bg-pink-500', textColor: 'text-white' };
    if (score >= 55) return { label: '一般', color: 'bg-yellow-500', textColor: 'text-black' };
    if (score >= 40) return { label: '较差', color: 'bg-orange-500', textColor: 'text-white' };
    return { label: '危险', color: 'bg-gray-500', textColor: 'text-white' };
  };

  const level = getScoreLevel(totalScore);

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-5 h-5" />
          <span className="font-medium">封板质量评分</span>
        </div>
        {onClose && (
          <button
            className="p-1 hover:bg-black/10 rounded"
            onClick={onClose}
          >
            ✕
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* 总体评分 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Badge className={`${level.color} ${level.textColor} px-3 py-1 text-lg`}>
              {totalScore}
            </Badge>
            <div>
              <p className="text-lg font-bold">{level.label}</p>
              <p className="text-xs text-muted-foreground">/100分</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">{stock.name}</p>
            <p className="text-sm text-muted-foreground">{stock.code}</p>
          </div>
        </div>

        {/* 评分进度条 */}
        <div className="relative h-3 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`absolute h-full ${level.color} transition-all duration-500`}
            style={{ width: `${totalScore}%` }}
          />
        </div>

        {/* 评分明细 */}
        <div className="space-y-3">
          {scoreItems.map((item) => (
            <div key={item.label} className="flex items-center gap-3">
              <item.icon className="w-4 h-4 text-muted-foreground" />
              <div className="flex-1">
                <div className="flex items-center justify-between text-sm mb-1">
                  <span>{item.label}</span>
                  <span className="text-muted-foreground">
                    {Math.round((item.value / 100) * item.maxScore)}/{item.maxScore}分
                  </span>
                </div>
                <div className="relative h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`absolute h-full ${
                      item.value >= 70 ? 'bg-green-500' : item.value >= 50 ? 'bg-yellow-500' : 'bg-red-500'
                    } transition-all duration-500`}
                    style={{ width: `${item.value}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground mt-1">{item.description}</p>
              </div>
            </div>
          ))}
        </div>

        {/* 风险提示 */}
        {stock.openCount > 1 && (
          <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-orange-500 mt-0.5" />
            <p className="text-sm text-orange-600 dark:text-orange-400">
              该股已开板{stock.openCount}次，封板质量有所下降，建议谨慎参与
            </p>
          </div>
        )}

        {/* 股票基本信息 */}
        <div className="grid grid-cols-2 gap-2 text-sm bg-muted/30 rounded-lg p-3">
          <div className="flex justify-between">
            <span className="text-muted-foreground">现价</span>
            <span>{stock.closePrice.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">涨停价</span>
            <span>{stock.limitUpPrice.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">涨幅</span>
            <span className="text-red-500">+{stock.changePct.toFixed(2)}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">换手率</span>
            <span>{stock.turnoverRate.toFixed(2)}%</span>
          </div>
        </div>

        {/* 建议 */}
        <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
          <p className="text-sm font-medium text-blue-600 dark:text-blue-400 mb-1">
            建议
          </p>
          <p className="text-sm text-muted-foreground">
            {totalScore >= 80
              ? '封板质量优秀，可以适当参与，控制仓位'
              : totalScore >= 60
              ? '封板质量一般，谨慎参与，仓位不宜过重'
              : '封板质量较差，不建议参与'}
          </p>
        </div>
      </div>
    </Card>
  );
}
