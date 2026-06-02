import { useState, useEffect, useCallback } from 'react';
import {
  Database, Wifi, WifiOff, AlertCircle, CheckCircle2, RefreshCw,
  ChevronDown, ChevronUp, Server, Zap, Search,
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Loading } from '@/components/common/Loading';
import { sealPlateApi } from '@/api/sealPlate';
import type { DataSourceHealthResponse } from '@/types/sealPlate';

// ============ 数据源元信息 ============

interface DataSourceMeta {
  name: string;
  displayName: string;
  category: 'kline' | 'realtime' | 'screening' | 'hotspot';
  coreAdvantages: string[];
  mainDrawbacks: string[];
  suitableFor: string;
  priority: number;
  enabled: boolean;
}

const DATA_SOURCES: DataSourceMeta[] = [
  {
    name: 'mootdx',
    displayName: 'mootdx (通达信)',
    category: 'realtime',
    coreAdvantages: ['IP友好', '盘口/K线稳定', 'TCP协议低延迟'],
    mainDrawbacks: ['功能单一', '无新闻/公告'],
    suitableFor: '量化交易、实盘行情',
    priority: 2,
    enabled: true,
  },
  {
    name: 'TencentFetcher',
    displayName: '腾讯财经',
    category: 'realtime',
    coreAdvantages: ['公开免费', '调用简单', '响应速度快'],
    mainDrawbacks: ['无官方文档', '接口可能变动'],
    suitableFor: '临时拉取、轻量监控',
    priority: 3,
    enabled: true,
  },
  {
    name: 'AkshareFetcher',
    displayName: 'akshare',
    category: 'kline',
    coreAdvantages: ['数据全面', 'Python友好', '社区活跃'],
    mainDrawbacks: ['部分接口依赖第三方', '稳定性有波动'],
    suitableFor: '多维度量化研究、回测',
    priority: 1,
    enabled: true,
  },
  {
    name: 'IwenCaiFetcher',
    displayName: 'i问财',
    category: 'screening',
    coreAdvantages: ['自然语言搜索', '选股能力强'],
    mainDrawbacks: ['需API Key', '调用频率受限'],
    suitableFor: '快速选股、策略验证',
    priority: 0,
    enabled: true,
  },
  {
    name: 'THSHotspotFetcher',
    displayName: '同花顺热点',
    category: 'hotspot',
    coreAdvantages: ['零鉴权', '实时热点数据'],
    mainDrawbacks: ['接口不稳定', '无历史数据'],
    suitableFor: '短线热点监控',
    priority: 0,
    enabled: true,
  },
  {
    name: 'TushareFetcher',
    displayName: 'tushare',
    category: 'kline',
    coreAdvantages: ['数据标准', '覆盖面广', '文档完善'],
    mainDrawbacks: ['积分墙限制多', '免费用户体验差'],
    suitableFor: '预算充足的机构/个人',
    priority: 0,
    enabled: true,
  },
  {
    name: 'Ashare',
    displayName: 'Ashare (已停更)',
    category: 'kline',
    coreAdvantages: ['曾是轻量行情库'],
    mainDrawbacks: ['接口失效', '无维护'],
    suitableFor: '不推荐使用',
    priority: 99,
    enabled: false,
  },
];

const CATEGORY_LABELS: Record<string, string> = {
  kline: 'K线/历史行情',
  realtime: '实时行情',
  screening: '智能选股',
  hotspot: '热点分析',
};

const CATEGORY_COLORS: Record<string, string> = {
  kline: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  realtime: 'bg-green-500/10 text-green-400 border-green-500/30',
  screening: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  hotspot: 'bg-orange-500/10 text-orange-400 border-orange-500/30',
};

// ============ 组件 ============

export default function DataSourcePanel() {
  const [health, setHealth] = useState<DataSourceHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSource, setExpandedSource] = useState<string | null>(null);

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await sealPlateApi.getDataSourcesHealth();
      setHealth(data);
    } catch (err: any) {
      setError(err?.message || '获取数据源状态失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  // 将后端健康数据映射到数据源元信息
  const getSourceHealth = (sourceName: string) => {
    if (!health?.sources) return null;
    return health.sources[sourceName] || null;
  };

  const getStatusIcon = (sourceName: string) => {
    const meta = DATA_SOURCES.find(s => s.name === sourceName);
    if (meta && !meta.enabled) {
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
    }
    const h = getSourceHealth(sourceName);
    if (!h) return <WifiOff className="h-4 w-4 text-gray-500" />;
    return h.available
      ? <CheckCircle2 className="h-4 w-4 text-green-400" />
      : <AlertCircle className="h-4 w-4 text-red-400" />;
  };

  const getStatusText = (sourceName: string) => {
    const meta = DATA_SOURCES.find(s => s.name === sourceName);
    if (meta && !meta.enabled) return '已停用';
    const h = getSourceHealth(sourceName);
    if (!h) return '未知';
    return h.available ? '可用' : '不可用';
  };

  const getStatusColor = (sourceName: string) => {
    const meta = DATA_SOURCES.find(s => s.name === sourceName);
    if (meta && !meta.enabled) return 'bg-gray-500/20 text-gray-400';
    const h = getSourceHealth(sourceName);
    if (!h) return 'bg-gray-500/20 text-gray-400';
    return h.available
      ? 'bg-green-500/20 text-green-400'
      : 'bg-red-500/20 text-red-400';
  };

  // 分组
  const grouped = DATA_SOURCES.reduce((acc, src) => {
    if (!acc[src.category]) acc[src.category] = [];
    acc[src.category].push(src);
    return acc;
  }, {} as Record<string, DataSourceMeta[]>);

  if (loading && !health) {
    return (
      <div className="flex justify-center py-20">
        <Loading label="正在检查数据源状态..." />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 总体状态 */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${
              health?.status === 'healthy' ? 'bg-green-500/10' :
              health?.status === 'degraded' ? 'bg-yellow-500/10' :
              'bg-red-500/10'
            }`}>
              <Database className={`h-5 w-5 ${
                health?.status === 'healthy' ? 'text-green-400' :
                health?.status === 'degraded' ? 'text-yellow-400' :
                'text-red-400'
              }`} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-white">数据源状态总览</h3>
              <p className="text-sm text-gray-400">
                {health
                  ? `${health.availableSources}/${health.totalSources} 个可用`
                  : '检查中...'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={
              health?.status === 'healthy' ? 'success' :
              health?.status === 'degraded' ? 'warning' :
              'danger'
            }>
              {health?.status === 'healthy' ? '正常' :
               health?.status === 'degraded' ? '部分降级' :
               '异常'}
            </Badge>
            <Button variant="ghost" size="sm" onClick={fetchHealth} isLoading={loading}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 进度条 */}
        <div className="w-full bg-gray-700 rounded-full h-2 mb-2">
          <div
            className={`h-2 rounded-full transition-all duration-500 ${
              health?.status === 'healthy' ? 'bg-green-500' :
              health?.status === 'degraded' ? 'bg-yellow-500' :
              'bg-red-500'
            }`}
            style={{
              width: health
                ? `${(health.availableSources / Math.max(health.totalSources, 1)) * 100}%`
                : '0%',
            }}
          />
        </div>

        {error && (
          <div className="mt-3 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            {error}
          </div>
        )}
      </Card>

      {/* 按分类展示 */}
      {Object.entries(grouped).map(([category, sources]) => (
        <Card key={category} className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <Badge className={CATEGORY_COLORS[category] || ''}>
              {CATEGORY_LABELS[category] || category}
            </Badge>
            <span className="text-xs text-gray-500">
              {sources.filter(s => s.enabled).length} 个启用
            </span>
          </div>

          <div className="space-y-3">
            {sources.map((source) => {
              const isExpanded = expandedSource === source.name;
              const h = getSourceHealth(source.name);

              return (
                <div
                  key={source.name}
                  className={`rounded-lg border transition-colors ${
                    source.enabled ? 'border-gray-700/50 bg-gray-800/30' : 'border-gray-800 bg-gray-800/10 opacity-50'
                  }`}
                >
                  {/* 行头 */}
                  <button
                    className="w-full flex items-center justify-between p-4 text-left"
                    onClick={() => setExpandedSource(isExpanded ? null : source.name)}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      {getStatusIcon(source.name)}
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white truncate">
                            {source.displayName}
                          </span>
                          <Badge className={getStatusColor(source.name)}>
                            {getStatusText(source.name)}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5">
                          适用: {source.suitableFor}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      {h && source.enabled && (
                        <span className="text-xs text-gray-500">
                          {(h.successRate * 100).toFixed(0)}%
                        </span>
                      )}
                      {isExpanded
                        ? <ChevronUp className="h-4 w-4 text-gray-500" />
                        : <ChevronDown className="h-4 w-4 text-gray-500" />
                      }
                    </div>
                  </button>

                  {/* 展开详情 */}
                  {isExpanded && (
                    <div className="px-4 pb-4 space-y-3 border-t border-gray-700/30 pt-3">
                      {/* 核心优势 */}
                      <div>
                        <h4 className="text-xs font-semibold text-green-400 mb-2 flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> 核心优势
                        </h4>
                        <ul className="space-y-1">
                          {source.coreAdvantages.map((adv, i) => (
                            <li key={i} className="text-xs text-gray-300 flex items-start gap-2">
                              <span className="text-green-400 mt-0.5">+</span>
                              {adv}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* 主要短板 */}
                      <div>
                        <h4 className="text-xs font-semibold text-red-400 mb-2 flex items-center gap-1">
                          <AlertCircle className="h-3 w-3" /> 主要短板
                        </h4>
                        <ul className="space-y-1">
                          {source.mainDrawbacks.map((draw, i) => (
                            <li key={i} className="text-xs text-gray-300 flex items-start gap-2">
                              <span className="text-red-400 mt-0.5">-</span>
                              {draw}
                            </li>
                          ))}
                        </ul>
                      </div>

                      {/* 健康详情 */}
                      {h && (
                        <div className="pt-2 border-t border-gray-700/30">
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="text-gray-400">
                              成功率: <span className="text-white">{(h.successRate * 100).toFixed(0)}%</span>
                            </div>
                            <div className="text-gray-400">
                              状态: <span className={h.available ? 'text-green-400' : 'text-red-400'}>
                                {h.available ? '可用' : '不可用'}
                              </span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Card>
      ))}

      {/* 数据源在决策中的角色 */}
      <Card className="p-6">
        <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
          <Zap className="h-4 w-4 text-cyan-400" />
          数据源决策角色
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="p-3 bg-blue-500/5 border border-blue-500/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Server className="h-4 w-4 text-blue-400" />
              <span className="text-xs font-medium text-blue-400">K线/历史行情</span>
            </div>
            <p className="text-xs text-gray-400">
              akshare (主) → tushare (备) → mootdx (通达信)
            </p>
            <p className="text-xs text-gray-500 mt-1">支撑技术分析、回测、策略验证</p>
          </div>

          <div className="p-3 bg-green-500/5 border border-green-500/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Wifi className="h-4 w-4 text-green-400" />
              <span className="text-xs font-medium text-green-400">实时行情</span>
            </div>
            <p className="text-xs text-gray-400">
              腾讯财经 (主) → mootdx (备) → akshare
            </p>
            <p className="text-xs text-gray-500 mt-1">实时价格、量比、换手率、盘口数据</p>
          </div>

          <div className="p-3 bg-purple-500/5 border border-purple-500/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Search className="h-4 w-4 text-purple-400" />
              <span className="text-xs font-medium text-purple-400">智能选股</span>
            </div>
            <p className="text-xs text-gray-400">
              i问财 — 自然语言选股
            </p>
            <p className="text-xs text-gray-500 mt-1">强势股筛选、连板检测、动量选股</p>
          </div>

          <div className="p-3 bg-orange-500/5 border border-orange-500/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <FlameIcon className="h-4 w-4 text-orange-400" />
              <span className="text-xs font-medium text-orange-400">热点分析</span>
            </div>
            <p className="text-xs text-gray-400">
              同花顺热点 — 概念热度
            </p>
            <p className="text-xs text-gray-500 mt-1">资金流向、板块轮动、情绪研判</p>
          </div>
        </div>
      </Card>
    </div>
  );
}

// 简单火焰图标
function FlameIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2c-3 4-6 8-6 12a6 6 0 0 0 12 0c0-4-3-8-6-12z" />
    </svg>
  );
}
