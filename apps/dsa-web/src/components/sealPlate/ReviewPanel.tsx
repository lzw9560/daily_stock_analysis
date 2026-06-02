import { useState, useEffect, useCallback } from 'react';
import {
  Brain, TrendingUp, TrendingDown, Target, Lightbulb, AlertTriangle,
  Shield, ChevronRight, ChevronDown, RefreshCw, Zap, Clock,
  BarChart3, Layers, Sparkles, MessageSquare, History,
} from 'lucide-react';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Loading } from '@/components/common/Loading';
import { EmptyState } from '@/components/common/EmptyState';
import { sealPlateApi } from '@/api/sealPlate';
import type {
  ReviewDetailResponse, ReviewHistoryItem,
  AutoReviewResponse, StrategyEvolutionResponse,
} from '@/types/sealPlate';

export default function ReviewPanel() {
  // 状态
  const [loading, setLoading] = useState(false);
  const [autoReviewing, setAutoReviewing] = useState(false);
  const [review, setReview] = useState<ReviewDetailResponse | null>(null);
  const [history, setHistory] = useState<ReviewHistoryItem[]>([]);
  const [evolution, setEvolution] = useState<StrategyEvolutionResponse['evolution']>([]);
  const [error, setError] = useState<string | null>(null);

  // 展开状态
  const [showSuccessPatterns, setShowSuccessPatterns] = useState(true);
  const [showFailurePatterns, setShowFailurePatterns] = useState(true);
  const [showStrategyAdjustments, setShowStrategyAdjustments] = useState(true);
  const [showEvolution, setShowEvolution] = useState(false);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notesDraft, setNotesDraft] = useState('');

  // 获取最新复盘数据
  const fetchReview = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [detail, hist, evo] = await Promise.all([
        sealPlateApi.getReviewDetail(),
        sealPlateApi.getReviewHistory(10),
        sealPlateApi.getStrategyEvolution(20),
      ]);
      setReview(detail);
      setHistory(hist.items);
      setEvolution(evo.evolution);
    } catch (e: any) {
      if (e?.response?.status === 404) {
        setReview(null);
        setError(null); // 还没复盘数据，不算错误
      } else {
        setError(e?.message || '加载复盘数据失败');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // 触发自动复盘
  const handleAutoReview = async () => {
    setAutoReviewing(true);
    try {
      const result: AutoReviewResponse = await sealPlateApi.triggerAutoReview();
      if (result.status !== 'noop') {
        // 刷新数据
        await fetchReview();
      }
    } catch (e: any) {
      setError(e?.message || '自动复盘失败');
    } finally {
      setAutoReviewing(false);
    }
  };

  // 保存备注
  const handleSaveNotes = async () => {
    if (!review) return;
    try {
      await sealPlateApi.updateReviewNotes(review.date, notesDraft);
      setReview({ ...review, notes: notesDraft });
      setEditingNotes(false);
    } catch (e: any) {
      setError(e?.message || '保存备注失败');
    }
  };

  useEffect(() => {
    fetchReview();
  }, [fetchReview]);

  // ---------- 空状态 ----------
  if (!loading && !review) {
    return (
      <div className="space-y-4">
        <EmptyState
          icon={<Brain className="h-12 w-12 text-muted-foreground" />}
          title="暂无复盘数据"
          description="需要至少3天以上的推荐记录和结算数据后，才能触发LLM复盘分析。"
          action={
            <div className="flex gap-3 justify-center mt-4">
              <Button onClick={fetchReview} variant="outline">
                <RefreshCw className="h-4 w-4 mr-2" />
                刷新
              </Button>
              <Button onClick={handleAutoReview} isLoading={autoReviewing}>
                <Zap className="h-4 w-4 mr-2" />
                立即复盘
              </Button>
            </div>
          }
        />
      </div>
    );
  }

  if (loading) {
    return <Loading label="正在加载复盘分析..." />;
  }

  // 趋势图标映射
  const getTrendBadge = (rate: number) => {
    if (rate >= 60) return <Badge variant="success">高胜率 {rate}%</Badge>;
    if (rate >= 40) return <Badge variant="default">中等 {rate}%</Badge>;
    return <Badge variant="danger">低胜率 {rate}%</Badge>;
  };

  return (
    <div className="space-y-4">
      {/* 错误提示 */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
          <button className="ml-2 underline" onClick={() => setError(null)}>关闭</button>
        </div>
      )}

      {/* ===== 顶部操作栏 ===== */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-purple-500" />
          <h3 className="text-lg font-semibold">
            LLM智能复盘
            {review?.modelUsed && (
              <span className="text-xs text-muted-foreground ml-2 font-normal">
                ({review.modelUsed})
              </span>
            )}
          </h3>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchReview} isLoading={loading}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button size="sm" onClick={handleAutoReview} isLoading={autoReviewing}>
            <Zap className="h-4 w-4 mr-1" />
            立即复盘
          </Button>
        </div>
      </div>

      {/* ===== 核心指标卡片 ===== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-3">
          <div className="text-xs text-muted-foreground mb-1">已结算笔数</div>
          <div className="text-2xl font-bold">{review?.settledCount || 0}</div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground mb-1">胜率</div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold">{(review?.winRate || 0).toFixed(1)}%</span>
            {getTrendBadge(review?.winRate || 0)}
          </div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground mb-1">平均收益</div>
          <div className={`text-2xl font-bold ${(review?.avgReturn || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {(review?.avgReturn || 0) >= 0 ? '+' : ''}{(review?.avgReturn || 0).toFixed(2)}%
          </div>
        </Card>
        <Card className="p-3">
          <div className="text-xs text-muted-foreground mb-1">推荐评分门槛</div>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold">{review?.recommendedMinScore || 65}</span>
            <span className="text-xs text-muted-foreground">置信度: {review?.recommendedConfidenceThreshold || '中'}</span>
          </div>
        </Card>
      </div>

      {/* ===== LLM 核心结论 ===== */}
      <Card className="p-4 border-l-4 border-l-purple-500 bg-purple-50/50">
        <div className="flex items-start gap-3">
          <Sparkles className="h-5 w-5 text-purple-600 mt-0.5 flex-shrink-0" />
          <div className="flex-1">
            <div className="text-sm font-medium text-purple-900 mb-1">LLM核心结论</div>
            <p className="text-sm text-purple-800">{review?.summary || '暂无'}</p>
            {review?.overallAssessment && (
              <p className="text-xs text-purple-600 mt-2">{review.overallAssessment}</p>
            )}
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* ===== 左列：模式识别 + 策略建议 ===== */}
        <div className="space-y-4">

          {/* 成功模式 */}
          {(review?.successPatterns?.length || 0) > 0 && (
            <Card className="p-4">
              <button
                className="flex items-center justify-between w-full"
                onClick={() => setShowSuccessPatterns(!showSuccessPatterns)}
              >
                <div className="flex items-center gap-2">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                  <span className="font-semibold text-sm">成功模式识别</span>
                  <Badge variant="default">{review?.successPatterns?.length || 0}项</Badge>
                </div>
                {showSuccessPatterns ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {showSuccessPatterns && (
                <ul className="mt-3 space-y-2">
                  {review?.successPatterns?.map((pattern, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Target className="h-4 w-4 text-green-500 mt-0.5 flex-shrink-0" />
                      <span className="text-muted-foreground">{pattern}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* 失败模式 */}
          {(review?.failurePatterns?.length || 0) > 0 && (
            <Card className="p-4">
              <button
                className="flex items-center justify-between w-full"
                onClick={() => setShowFailurePatterns(!showFailurePatterns)}
              >
                <div className="flex items-center gap-2">
                  <TrendingDown className="h-4 w-4 text-red-600" />
                  <span className="font-semibold text-sm">失败模式分析</span>
                  <Badge variant="default">{review?.failurePatterns?.length || 0}项</Badge>
                </div>
                {showFailurePatterns ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {showFailurePatterns && (
                <ul className="mt-3 space-y-2">
                  {review?.failurePatterns?.map((pattern, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <AlertTriangle className="h-4 w-4 text-red-500 mt-0.5 flex-shrink-0" />
                      <span className="text-muted-foreground">{pattern}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* 策略调整建议 */}
          {(review?.strategyAdjustments?.length || 0) > 0 && (
            <Card className="p-4">
              <button
                className="flex items-center justify-between w-full"
                onClick={() => setShowStrategyAdjustments(!showStrategyAdjustments)}
              >
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  <span className="font-semibold text-sm">LLM策略调整建议</span>
                  <Badge variant="default">{review?.strategyAdjustments?.length || 0}项</Badge>
                </div>
                {showStrategyAdjustments ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
              </button>
              {showStrategyAdjustments && (
                <ul className="mt-3 space-y-2">
                  {review?.strategyAdjustments?.map((adj, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm bg-yellow-50 rounded-lg p-2">
                      <Lightbulb className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                      <span className="text-yellow-800">{adj}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {/* 评分权重建言 */}
          {(review?.scoreWeightSuggestions?.length || 0) > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="h-4 w-4 text-blue-500" />
                <span className="font-semibold text-sm">评分权重建言</span>
              </div>
              <ul className="space-y-2">
                {review?.scoreWeightSuggestions?.map((s, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <BarChart3 className="h-4 w-4 text-blue-400 mt-0.5 flex-shrink-0" />
                    <span className="text-muted-foreground">{s}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        {/* ===== 右列：板块洞察 + 仓位建议 + 策略演化 ===== */}
        <div className="space-y-4">

          {/* 仓位建议 */}
          <Card className="p-4 border-l-4 border-l-blue-500">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-4 w-4 text-blue-600" />
              <span className="font-semibold text-sm">仓位管理建议</span>
            </div>
            <p className="text-sm text-muted-foreground">{review?.positionAdvice || '暂无仓位建议'}</p>
          </Card>

          {/* 高动量板块 */}
          {(review?.highMomentumSectors?.length || 0) > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="h-4 w-4 text-green-600" />
                <span className="font-semibold text-sm">高胜率可持续板块</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {review?.highMomentumSectors?.map((s, i) => (
                  <Badge key={i} variant="success">{s}</Badge>
                ))}
              </div>
            </Card>
          )}

          {/* 风险板块 */}
          {(review?.riskSectors?.length || 0) > 0 && (
            <Card className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="h-4 w-4 text-red-500" />
                <span className="font-semibold text-sm">需要回避的板块</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {review?.riskSectors?.map((s, i) => (
                  <Badge key={i} variant="danger">{s}</Badge>
                ))}
              </div>
            </Card>
          )}

          {/* 策略演化时间线 */}
          <Card className="p-4">
            <button
              className="flex items-center justify-between w-full"
              onClick={() => setShowEvolution(!showEvolution)}
            >
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-indigo-500" />
                <span className="font-semibold text-sm">策略演化追踪</span>
                {evolution.length > 0 && (
                  <Badge variant="default">{evolution.length}个版本</Badge>
                )}
              </div>
              {showEvolution ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </button>
            {showEvolution && (
              <div className="mt-3 space-y-2 max-h-60 overflow-y-auto">
                {evolution.length > 0 ? (
                  evolution.map((evo, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs p-2 bg-muted/50 rounded-lg">
                      <Clock className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                      <span className="font-mono text-muted-foreground">{evo.date}</span>
                      <span className="text-muted-foreground">→</span>
                      <span className="font-medium">≥{evo.minScore}分</span>
                      <span className="text-muted-foreground">|</span>
                      <span>{evo.confidence}置信</span>
                      <span className="text-muted-foreground">|</span>
                      <span>≤{evo.maxRecs}只</span>
                      {evo.winRate > 0 && (
                        <>
                          <span className="text-muted-foreground">|</span>
                          <span className={evo.winRate >= 50 ? 'text-green-600' : 'text-red-600'}>
                            胜率{evo.winRate.toFixed(0)}%
                          </span>
                        </>
                      )}
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground py-4 text-center">
                    暂无策略演化数据，多次复盘后将自动追踪参数调整历程
                  </p>
                )}
              </div>
            )}
          </Card>

          {/* 备注 */}
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-gray-500" />
                <span className="font-semibold text-sm">复盘备注</span>
              </div>
              {!editingNotes && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setNotesDraft(review?.notes || '');
                    setEditingNotes(true);
                  }}
                >
                  编辑
                </Button>
              )}
            </div>
            {editingNotes ? (
              <div className="space-y-2">
                <textarea
                  className="w-full border rounded-lg p-2 text-sm min-h-[80px]"
                  value={notesDraft}
                  onChange={(e) => setNotesDraft(e.target.value)}
                  placeholder="记录你的复盘思考..."
                />
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="sm" onClick={() => setEditingNotes(false)}>
                    取消
                  </Button>
                  <Button size="sm" onClick={handleSaveNotes}>
                    保存
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {review?.notes || '暂无备注，点击编辑添加你的复盘笔记'}
              </p>
            )}
          </Card>
        </div>
      </div>

      {/* ===== 复盘历史列表 ===== */}
      {history.length > 1 && (
        <Card className="p-4 mt-4">
          <div className="flex items-center gap-2 mb-3">
            <History className="h-4 w-4 text-gray-500" />
            <span className="font-semibold text-sm">复盘历史</span>
          </div>
          <div className="space-y-1 max-h-60 overflow-y-auto">
            {history.slice(1).map((item) => (
              <div
                key={item.date}
                className="flex items-center gap-3 text-xs p-2 hover:bg-muted/50 rounded-lg cursor-pointer"
              >
                <span className="font-mono text-muted-foreground w-24">{item.date}</span>
                <div className="flex-1 min-w-0">
                  <span className="truncate block">{item.summary || '(无总结)'}</span>
                </div>
                {item.hasLlmAnalysis && (
                  <Badge variant="default" className="text-xs">
                    <Brain className="h-3 w-3 mr-1" />
                    LLM
                  </Badge>
                )}
                <span className={item.winRate >= 50 ? 'text-green-600' : 'text-red-600'}>
                  {item.winRate.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
