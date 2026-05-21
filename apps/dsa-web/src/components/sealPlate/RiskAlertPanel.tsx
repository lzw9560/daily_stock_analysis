import { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, AlertCircle, RefreshCw, X } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { RiskAlert } from '@/types/sealPlate';

function AlertCard({
  alert,
  onDismiss
}: {
  alert: RiskAlert;
  onDismiss?: () => void;
}) {
  const isRed = alert.maxLevel === 'red';

  return (
    <div
      className={`rounded-lg p-4 border ${
        isRed
          ? 'bg-red-500/10 border-red-500/30'
          : 'bg-yellow-500/10 border-yellow-500/30'
      }`}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {isRed ? (
            <AlertTriangle className="w-5 h-5 text-red-500" />
          ) : (
            <AlertCircle className="w-5 h-5 text-yellow-500" />
          )}
          <span className="font-medium">{alert.name}</span>
          <span className="text-sm text-muted-foreground">{alert.code}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={alert.score >= 70 ? 'success' : 'warning'}>
            {alert.score}分
          </Badge>
          {onDismiss && (
            <button
              className="p-1 hover:bg-black/10 rounded"
              onClick={onDismiss}
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <div className="space-y-1">
        {alert.conditions.map((condition, index) => (
          <p
            key={index}
            className={`text-sm ${
              condition.level === 'red'
                ? 'text-red-600 dark:text-red-400'
                : 'text-yellow-600 dark:text-yellow-400'
            }`}
          >
            • {condition.message}
          </p>
        ))}
      </div>

      <div className="mt-3 pt-3 border-t border-current/20">
        <p className={`text-sm font-medium ${
          isRed
            ? 'text-red-600 dark:text-red-400'
            : 'text-yellow-600 dark:text-yellow-400'
        }`}>
          建议: {isRed ? '立即减仓或清仓' : '密切关注，准备减仓'}
        </p>
      </div>
    </div>
  );
}

export default function RiskAlertPanel() {
  const [alerts, setAlerts] = useState<RiskAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    try {
      const data = await sealPlateApi.getRiskAlerts();
      setAlerts(data.alerts);
    } catch (error) {
      console.error('获取风险预警失败:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    // 每分钟刷新一次
    const interval = setInterval(fetchAlerts, 60000);
    return () => clearInterval(interval);
  }, [fetchAlerts]);

  const handleDismiss = (code: string) => {
    setDismissed((prev) => new Set(prev).add(code));
  };

  const visibleAlerts = alerts.filter((a) => !dismissed.has(a.code));
  const redAlerts = visibleAlerts.filter((a) => a.maxLevel === 'red');
  const yellowAlerts = visibleAlerts.filter((a) => a.maxLevel === 'yellow');

  if (loading && alerts.length === 0) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载风险预警..." />
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-orange-500" />
          <span className="font-medium">炸板风险预警</span>
          {visibleAlerts.length > 0 && (
            <Badge variant="danger" className="ml-2">
              {visibleAlerts.length}
            </Badge>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={fetchAlerts}
          disabled={loading}
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <div className="space-y-4">
        {visibleAlerts.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>暂无风险预警</p>
            <p className="text-xs">当前市场封板质量良好</p>
          </div>
        ) : (
          <>
            {/* 红色预警 */}
            {redAlerts.length > 0 && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-red-500 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  红色预警 ({redAlerts.length})
                </p>
                {redAlerts.map((alert) => (
                  <AlertCard
                    key={alert.code}
                    alert={alert}
                    onDismiss={() => handleDismiss(alert.code)}
                  />
                ))}
              </div>
            )}

            {/* 黄色预警 */}
            {yellowAlerts.length > 0 && (
              <div className="space-y-3">
                <p className="text-sm font-medium text-yellow-500 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  黄色预警 ({yellowAlerts.length})
                </p>
                {yellowAlerts.map((alert) => (
                  <AlertCard
                    key={alert.code}
                    alert={alert}
                    onDismiss={() => handleDismiss(alert.code)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* 预警条件说明 */}
        <div className="bg-muted/30 rounded-lg p-3 text-xs space-y-1">
          <p className="font-medium text-muted-foreground">预警触发条件:</p>
          <p className="text-muted-foreground">• 封单金额5分钟内减少&gt;30%</p>
          <p className="text-muted-foreground">• 出现单笔&gt;5000手卖单砸盘</p>
          <p className="text-muted-foreground">• 同板块龙头股炸板</p>
          <p className="text-muted-foreground">• 封单金额&lt;流通市值0.3%</p>
        </div>
      </div>
    </Card>
  );
}
