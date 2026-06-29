import apiClient from './index';
import { systemConfigApi } from './systemConfig';
import { toCamelCase } from './utils';
import type {
  FactorPipelineRecordResponse,
  FactorPipelineTriggerRequest,
  FactorPipelineTriggerResponse,
} from '../types/screening';

const ALPHASIFT_SCREEN_TIMEOUT_MS = 180000;
const ALPHASIFT_INSTALL_TIMEOUT_MS = 300000;
export const ALPHASIFT_CONFIG_CHANGED_EVENT = 'alphasift-config-changed';
export const SYSTEM_CONFIG_CHANGED_EVENT = 'dsa-system-config-changed';

export type AlphaSiftStatus = {
  enabled: boolean;
  available: boolean;
  installSpecIsDefault: boolean;
  contractVersion?: string | null;
  version?: string | null;
  strategyCount?: number | null;
};

export type AlphaSiftInstallResponse = {
  installed: boolean;
  alreadyInstalled: boolean;
  installSpecIsDefault: boolean;
};

export type AlphaSiftCandidate = {
  id: number;
  rank: number;
  code: string;
  name: string;
  score?: number | null;
  screenScore?: number | null;
  reason: string;
  riskLevel?: string;
  riskFlags?: string[];
  llmScore?: number | null;
  llmConfidence?: number | null;
  llmSector?: string;
  llmTheme?: string;
  llmTags?: string[];
  llmThesis?: string;
  llmCatalysts?: string[];
  llmRisks?: string[];
  llmWatchItems?: string[];
  llmInvalidators?: string[];
  llmStyleFit?: string;
  price?: number | null;
  changePct?: number | null;
  amount?: number | null;
  industry?: string;
  factorScores?: Record<string, number>;
  postAnalysisSummaries?: Record<string, string>;
  postAnalysisTags?: string[];
  raw: Record<string, unknown>;
};

export type AlphaSiftStrategy = {
  id: string;
  name: string;
  title?: string;
  description: string;
  version?: string;
  category?: string;
  tag?: string;
  tags?: string[];
  marketScope?: string[];
  market?: string;
};

export type AlphaSiftStrategiesResponse = {
  enabled: boolean;
  strategies: AlphaSiftStrategy[];
  strategyCount: number;
};

export type AlphaSiftScreenResponse = {
  enabled: boolean;
  candidates: AlphaSiftCandidate[];
  candidateCount: number;
  runId?: string;
  strategy?: string;
  market?: string;
  snapshotCount?: number;
  afterFilterCount?: number;
  llmRanked?: boolean;
  llmMarketView?: string;
  llmSelectionLogic?: string;
  llmPortfolioRisk?: string;
  llmCoverage?: number | null;
  llmParseErrors?: string[];
  warnings?: string[];
  sourceErrors?: string[];
};

// History record types
export type ScreeningRecordItem = {
  id: number;
  screeningDate: string;
  strategy: string;
  market: string;
  candidateCount: number;
  status: 'completed' | 'failed';
  durationSeconds: number;
  runId?: string;
  createdAt: string;
};

export type ScreeningRecordsResponse = {
  total: number;
  limit: number;
  offset: number;
  records: ScreeningRecordItem[];
};

export type BacktestResultItem = {
  period?: string;
  totalReturn?: number;
  annualReturn?: number;
  maxDrawdown?: number;
  sharpeRatio?: number;
  winRate?: number;
  [key: string]: unknown;
};

export type BacktestSummary = {
  avgAnnualReturn?: number;
  avgMaxDrawdown?: number;
  avgSharpe?: number;
  avgWinRate?: number;
  [key: string]: unknown;
};

export type ScreeningRecordDetail = ScreeningRecordItem & {
  errorMessage?: string;
  snapshotCount?: number;
  afterFilterCount?: number;
  llmRanked?: boolean;
  llmMarketView?: string;
  llmSelectionLogic?: string;
  llmPortfolioRisk?: string;
  llmCoverage?: number | null;
  warnings?: string[];
  sourceErrors?: string[];
  executionLogs?: string;
  factorPipeline?: Record<string, unknown>;
  backtestResults?: BacktestResultItem[];
  backtestSummary?: BacktestSummary;
  candidates: AlphaSiftCandidate[];
};

export function notifyAlphaSiftConfigChanged(): void {
  window.dispatchEvent(new Event(ALPHASIFT_CONFIG_CHANGED_EVENT));
  notifySystemConfigChanged();
}

export function notifySystemConfigChanged(): void {
  window.dispatchEvent(new Event(SYSTEM_CONFIG_CHANGED_EVENT));
}

async function setAlphaSiftEnabled(value: 'true' | 'false'): Promise<void> {
  const config = await systemConfigApi.getConfig(false);
  await systemConfigApi.update({
    configVersion: config.configVersion,
    maskToken: config.maskToken,
    reloadNow: true,
    items: [{ key: 'ALPHASIFT_ENABLED', value }],
  });
  notifyAlphaSiftConfigChanged();
}

export const alphasiftApi = {
  async getStatus(): Promise<AlphaSiftStatus> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/alphasift/status');
    return toCamelCase<AlphaSiftStatus>(response.data);
  },

  async screen(payload: { market: string; strategy: string; maxResults: number }): Promise<AlphaSiftScreenResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/alphasift/screen', {
      market: payload.market,
      strategy: payload.strategy,
      max_results: payload.maxResults,
    }, { timeout: ALPHASIFT_SCREEN_TIMEOUT_MS });
    return toCamelCase<AlphaSiftScreenResponse>(response.data);
  },

  /** 一键运行所有策略（调用 POST /api/v1/screening/run） */
  async runBatch(payload: {
    strategies?: string[];
    market?: string;
    maxResults?: number;
    autoBacktest?: boolean;
    notifyFeishu?: boolean;
  } = {}): Promise<ScreeningRunResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/screening/run', {
      strategies: payload.strategies ?? null,
      market: payload.market ?? 'cn',
      max_results: payload.maxResults ?? 20,
      auto_backtest: payload.autoBacktest ?? true,
      notify_feishu: payload.notifyFeishu ?? false,
    }, { timeout: ALPHASIFT_SCREEN_TIMEOUT_MS * 2 });
    return toCamelCase<ScreeningRunResponse>(response.data);
  },

  async getStrategies(): Promise<AlphaSiftStrategiesResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/alphasift/strategies');
    return toCamelCase<AlphaSiftStrategiesResponse>(response.data);
  },

  async install(): Promise<AlphaSiftInstallResponse> {
    const response = await apiClient.post<Record<string, unknown>>('/api/v1/alphasift/install', {}, { timeout: ALPHASIFT_INSTALL_TIMEOUT_MS });
    return toCamelCase<AlphaSiftInstallResponse>(response.data);
  },

  async enable(): Promise<void> {
    await setAlphaSiftEnabled('true');
    try {
      const status = await alphasiftApi.getStatus();
      if (!status.available) {
        throw new Error('AlphaSift 适配层当前不可用。桌面发布包应已内置 AlphaSift；源码部署请先在后端 Python 环境安装 AlphaSift 后再开启选股。');
      }
    } catch (error) {
      try {
        await setAlphaSiftEnabled('false');
      } catch {
        // Preserve the original install/status failure for the caller.
      }
      throw error;
    }
  },

  async getRecords(params?: {
    screeningDate?: string;
    strategy?: string;
    market?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScreeningRecordsResponse> {
    const response = await apiClient.get<ScreeningRecordsResponse>('/api/v1/screening/records', { params });
    return toCamelCase<ScreeningRecordsResponse>(response.data);
  },

  async getRecordDetail(recordId: number): Promise<ScreeningRecordDetail> {
    const response = await apiClient.get<ScreeningRecordDetail>(`/api/v1/screening/records/${recordId}`);
    return toCamelCase<ScreeningRecordDetail>(response.data);
  },

  async getFactorPipeline(recordId: number): Promise<FactorPipelineRecordResponse> {
    const response = await apiClient.get<FactorPipelineRecordResponse>(
      `/api/v1/screening/records/${recordId}/factor-pipeline`,
    );
    return toCamelCase<FactorPipelineRecordResponse>(response.data);
  },

  async triggerFactorPipeline(params: FactorPipelineTriggerRequest): Promise<FactorPipelineTriggerResponse> {
    const response = await apiClient.post<FactorPipelineTriggerResponse>(
      '/api/v1/screening/factor-pipeline/run',
      { record_id: params.recordId, market: params.market, screening_date: params.screeningDate },
    );
    return toCamelCase<FactorPipelineTriggerResponse>(response.data);
  },
};

/** 批量运行响应类型 */
export type ScreeningRunResponse = {
  screeningDate: string;
  totalStrategies: number;
  completedStrategies: number;
  failedStrategies: number;
  totalCandidates: number;
  uniqueCodes: number;
  strategies: Array<{
    strategy: string;
    market: string;
    status: string;
    candidateCount: number;
    recordId?: number;
    error?: string;
    candidateCodes?: string[];
  }>;
  autoBacktest?: {
    status: string;
    error?: string;
  } | null;
};

/** AlphaSift 策略中文名称映射表 */
export const STRATEGY_NAME_CN: Record<string, string> = {
  dual_low: '双低策略',
  quality_value: '优质价值',
  volume_breakout: '放量突破',
  balanced_alpha: '均衡阿尔法',
  capital_heat: '资金热度',
  growth_at_reasonable_price: '合理价格成长',
  momentum_breakout: '动量突破',
  low_volatility_quality: '低波优质',
  deep_value: '深度价值',
  dividend_aristocrats: '红利贵族',
  quality_compounders: '优质复利',
  turnaround_opportunities: '困境反转',
};

/** 获取策略中文名 */
export const getStrategyNameCn = (key: string): string => STRATEGY_NAME_CN[key] || key;
