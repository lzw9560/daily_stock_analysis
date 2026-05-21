import { useState, useEffect } from 'react';
import { CheckCircle2, XCircle, AlertCircle, Shield, Info } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { EightStandardCheckResult } from '@/types/sealPlate';

interface Props {
  stockCode: string;
  stockName?: string;
  onClose?: () => void;
}

export default function EightStandardChecklist({ stockCode, onClose }: Props) {
  const [result, setResult] = useState<EightStandardCheckResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchCheck = async () => {
      setLoading(true);
      try {
        const data = await sealPlateApi.checkEightStandard(stockCode);
        setResult(data);
      } catch (error) {
        console.error('八项标准检查失败:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchCheck();
  }, [stockCode]);

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low':
        return 'bg-green-500/10 border-green-500/30 text-green-600 dark:text-green-400';
      case 'medium':
        return 'bg-yellow-500/10 border-yellow-500/30 text-yellow-600 dark:text-yellow-400';
      case 'high':
        return 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400';
      default:
        return 'bg-gray-500/10 border-gray-500/30';
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 15) return 'text-green-500';
    if (score >= 10) return 'text-yellow-500';
    return 'text-red-500';
  };

  if (loading) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <Loading label="正在检查八项标准..." />
        </div>
      </Card>
    );
  }

  if (!result) {
    return (
      <Card>
        <div className="flex items-center justify-center h-64">
          <p className="text-muted-foreground">检查失败</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className={`${getRiskColor(result.riskLevel)} border-2`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Shield className="w-5 h-5" />
          <span className="font-medium">打板决策检查表</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="default">
            {result.name} {result.code}
          </Badge>
          {onClose && (
            <button
              className="p-1 hover:bg-black/10 rounded"
              onClick={onClose}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* 总体评分 */}
        <div className="flex items-center justify-between bg-background/50 rounded-lg p-4">
          <div>
            <p className="text-sm text-muted-foreground">八项标准总分</p>
            <p className={`text-4xl font-bold ${getScoreColor(result.totalScore)}`}>
              {result.totalScore}
              <span className="text-lg text-muted-foreground">/100</span>
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-muted-foreground">通过/总计</p>
            <p className="text-2xl font-bold">
              <span className="text-green-500">{result.passedCount}</span>
              <span className="text-muted-foreground">/</span>
              <span className="text-red-500">{result.failedCount}</span>
            </p>
          </div>
        </div>

        {/* 检查项列表 */}
        <div className="space-y-2">
          {result.checks.map((check, index) => (
            <div
              key={index}
              className={`flex items-center gap-3 p-3 rounded-lg ${
                check.passed
                  ? 'bg-green-500/5 border border-green-500/20'
                  : 'bg-red-500/5 border border-red-500/20'
              }`}
            >
              {check.passed ? (
                <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
              ) : (
                <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{check.name}</span>
                  <span className="text-sm text-muted-foreground">
                    ({check.score}分)
                  </span>
                </div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="truncate">
                    实际: <strong>{check.actualValue}</strong>
                  </span>
                  {!check.passed && (
                    <span className="text-red-500 flex-shrink-0">
                      (期望: {check.expectedRange})
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* 系统建议 */}
        <div className={`rounded-lg p-4 ${getRiskColor(result.riskLevel)}`}>
          <div className="flex items-start gap-2">
            {result.riskLevel === 'low' ? (
              <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5" />
            ) : result.riskLevel === 'medium' ? (
              <AlertCircle className="w-5 h-5 text-yellow-500 mt-0.5" />
            ) : (
              <XCircle className="w-5 h-5 text-red-500 mt-0.5" />
            )}
            <div>
              <p className="font-medium mb-1">系统建议</p>
              <p className="text-sm">{result.suggestion}</p>
            </div>
          </div>
        </div>

        {/* 次日卖出纪律提醒 */}
        <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <Info className="w-5 h-5 text-blue-500 mt-0.5" />
            <div className="text-sm space-y-1">
              <p className="font-medium text-blue-600 dark:text-blue-400">次日卖出纪律</p>
              <p className="text-muted-foreground">
                • 高开≥4%: 建议分批卖出，不要等涨停
              </p>
              <p className="text-muted-foreground">
                • 平开/低开: 15分钟不翻红请果断离场
              </p>
              <p className="text-muted-foreground">
                • 低开&gt;2%: 竞价弱势，建议开盘即走
              </p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
