import { useState, useEffect, useCallback } from 'react';
import { Briefcase, RefreshCw, Shield } from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import type { HoldingsResponse } from '@/types/sealPlate';

export default function HoldingsPanel() {
  const [holdings, setHoldings] = useState<HoldingsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHoldings = useCallback(async () => {
    setLoading(true);
    try {
      const { sealPlateApi } = await import('@/api/sealPlate');
      const data = await sealPlateApi.getHoldings();
      setHoldings(data);
    } catch {
      // 从后端获取失败时使用默认持仓
      setHoldings({
        positions: [
          { code: '000000', name: '华丽家族', totalQty: 20000, availableQty: 10000, currentPrice: 2.790, costPrice: 2.691, totalPnl: 1984.46, dailyPnl: 3394.74 },
          { code: '000000', name: '宏盛股份', totalQty: 600, availableQty: 600, currentPrice: 60.810, costPrice: 69.242, totalPnl: -5059.41, dailyPnl: 606.00 },
          { code: '000000', name: '双良节能', totalQty: 6600, availableQty: 6600, currentPrice: 5.520, costPrice: 6.465, totalPnl: -6238.41, dailyPnl: 594.00 },
          { code: '000000', name: '大众交通', totalQty: 7300, availableQty: 7300, currentPrice: 4.770, costPrice: 5.737, totalPnl: -7056.42, dailyPnl: 292.00 },
          { code: '000000', name: '紫金矿业', totalQty: 3300, availableQty: 3300, currentPrice: 30.470, costPrice: 32.423, totalPnl: -6445.67, dailyPnl: 99.00 },
          { code: '000000', name: '格力电器', totalQty: 300, availableQty: 300, currentPrice: 38.880, costPrice: 39.317, totalPnl: -131.00, dailyPnl: -87.00 },
          { code: '000000', name: '浦发银行', totalQty: 2100, availableQty: 2100, currentPrice: 9.260, costPrice: 10.824, totalPnl: -3285.33, dailyPnl: -231.00 },
          { code: '000000', name: '中信重工', totalQty: 4000, availableQty: 4000, currentPrice: 5.490, costPrice: 5.893, totalPnl: -1610.23, dailyPnl: -280.00 },
          { code: '000000', name: '川润股份', totalQty: 1500, availableQty: 1500, currentPrice: 20.260, costPrice: 22.070, totalPnl: -2715.00, dailyPnl: -855.00 },
        ],
        totalPnl: -30557.01,
        totalDailyPnl: 3532.74,
        totalMarketValue: 0,
        totalCost: 0,
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHoldings();
  }, [fetchHoldings]);

  if (loading && !holdings) {
    return (
      <Card>
        <div className="flex items-center justify-center h-48">
          <Loading label="加载持仓数据..." />
        </div>
      </Card>
    );
  }

  const positions = holdings?.positions || [];
  const totalPnl = holdings?.totalPnl || 0;
  const totalDailyPnl = holdings?.totalDailyPnl || 0;

  // 计算统计
  const totalMarketValue = positions.reduce((s, p) => s + p.totalQty * p.currentPrice, 0);
  const totalCost = positions.reduce((s, p) => s + p.totalQty * p.costPrice, 0);
  const winCount = positions.filter(p => p.totalPnl > 0).length;
  const lossCount = positions.filter(p => p.totalPnl < 0).length;
  const winRate = positions.length > 0 ? (winCount / positions.length * 100) : 0;

  const formatMoney = (v: number) => {
    const abs = Math.abs(v);
    const sign = v >= 0 ? '+' : '-';
    if (abs >= 10000) return `${sign}${(abs / 10000).toFixed(2)}万`;
    return `${sign}${abs.toFixed(2)}`;
  };

  const formatPrice = (v: number) => v.toFixed(3);

  const getPnlColor = (v: number) => (v > 0 ? 'text-red-500' : v < 0 ? 'text-green-500' : 'text-muted-foreground');
  const getPnlBg = (v: number) => (v > 0 ? 'bg-red-500/5' : v < 0 ? 'bg-green-500/5' : '');

  return (
    <div className="space-y-6">
      {/* 持仓总览 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="text-center p-4">
          <div className="text-xs text-muted-foreground mb-1">持仓总数</div>
          <div className="text-2xl font-bold">{positions.length}<span className="text-sm font-normal">只</span></div>
          <div className="text-xs text-muted-foreground mt-1">胜{winCount}/负{lossCount} 胜率{winRate.toFixed(0)}%</div>
        </Card>
        <Card className="text-center p-4">
          <div className="text-xs text-muted-foreground mb-1">总市值</div>
          <div className="text-2xl font-bold">{(totalMarketValue / 10000).toFixed(2)}<span className="text-sm font-normal">万</span></div>
        </Card>
        <Card className={`text-center p-4 ${getPnlBg(totalPnl)}`}>
          <div className="text-xs text-muted-foreground mb-1">持仓盈亏</div>
          <div className={`text-2xl font-bold ${getPnlColor(totalPnl)}`}>
            {formatMoney(totalPnl)}
          </div>
        </Card>
        <Card className={`text-center p-4 ${getPnlBg(totalDailyPnl)}`}>
          <div className="text-xs text-muted-foreground mb-1">当日盈亏</div>
          <div className={`text-2xl font-bold ${getPnlColor(totalDailyPnl)}`}>
            {formatMoney(totalDailyPnl)}
          </div>
        </Card>
      </div>

      {/* 持仓明细表格 */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Briefcase className="w-5 h-5 text-blue-500" />
            <span className="font-medium">持仓明细</span>
          </div>
          <Button size="sm" variant="ghost" onClick={fetchHoldings} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>

        {positions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="py-3 px-2 font-medium">#</th>
                  <th className="py-3 px-2 font-medium">股票名称</th>
                  <th className="py-3 px-2 font-medium text-right">持仓</th>
                  <th className="py-3 px-2 font-medium text-right">可用</th>
                  <th className="py-3 px-2 font-medium text-right">现价</th>
                  <th className="py-3 px-2 font-medium text-right">成本价</th>
                  <th className="py-3 px-2 font-medium text-right">持仓盈亏</th>
                  <th className="py-3 px-2 font-medium text-right">当日盈亏</th>
                  <th className="py-3 px-2 font-medium text-center">盈亏率</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((pos, idx) => {
                  const pnlPct = pos.costPrice > 0 ? ((pos.currentPrice - pos.costPrice) / pos.costPrice * 100) : 0;
                  return (
                    <tr
                      key={idx}
                      className={`border-b border-border/50 hover:bg-accent/10 transition-colors ${
                        pos.totalPnl > 0 ? 'bg-red-500/[0.02]' : pos.totalPnl < 0 ? 'bg-green-500/[0.02]' : ''
                      }`}
                    >
                      <td className="py-2.5 px-2 text-muted-foreground">{idx + 1}</td>
                      <td className="py-2.5 px-2">
                        <span className="font-medium">{pos.name}</span>
                        <span className="text-xs text-muted-foreground ml-1">{pos.code}</span>
                      </td>
                      <td className="py-2.5 px-2 text-right">{pos.totalQty.toLocaleString()}</td>
                      <td className="py-2.5 px-2 text-right">{pos.availableQty.toLocaleString()}</td>
                      <td className="py-2.5 px-2 text-right font-mono">{formatPrice(pos.currentPrice)}</td>
                      <td className="py-2.5 px-2 text-right font-mono text-muted-foreground">{formatPrice(pos.costPrice)}</td>
                      <td className={`py-2.5 px-2 text-right font-mono font-medium ${getPnlColor(pos.totalPnl)}`}>
                        {formatMoney(pos.totalPnl)}
                      </td>
                      <td className={`py-2.5 px-2 text-right font-mono ${getPnlColor(pos.dailyPnl)}`}>
                        {pos.dailyPnl >= 0 ? '+' : ''}{pos.dailyPnl.toFixed(2)}
                      </td>
                      <td className="py-2.5 px-2 text-center">
                        <Badge variant={pnlPct > 0 ? 'success' : pnlPct < 0 ? 'danger' : 'default'}>
                          {pnlPct > 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                        </Badge>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Briefcase className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>暂无持仓数据</p>
          </div>
        )}
      </Card>

      {/* 仓位建议 */}
      {positions.length > 0 && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <div className="flex items-center gap-2 text-blue-600 mb-3">
            <Shield className="w-5 h-5" />
            <span className="font-medium">仓位管理建议</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">总市值</span>
              <span className="font-medium">{(totalMarketValue / 10000).toFixed(2)}万</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">总成本</span>
              <span className="font-medium">{(totalCost / 10000).toFixed(2)}万</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">盈利标的</span>
              <span className="text-red-500 font-medium">{winCount}只</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">亏损标的</span>
              <span className="text-green-500 font-medium">{lossCount}只</span>
            </div>
            <div className="pt-2 mt-2 border-t border-border">
              <p className="text-muted-foreground">
                {lossCount > winCount
                  ? '⚠️ 亏损标的较多，建议检查持仓质量，考虑止损亏损较大的标的'
                  : winRate >= 50
                    ? '✅ 持仓结构合理，继续按策略执行'
                    : '📊 持仓表现一般，建议优化选股策略'}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* 风险更新状态 */}
      {holdings?.updatedAt && (
        <div className="text-center text-xs text-muted-foreground">
          数据更新时间: {new Date(holdings.updatedAt).toLocaleString('zh-CN')}
        </div>
      )}
    </div>
  );
}
