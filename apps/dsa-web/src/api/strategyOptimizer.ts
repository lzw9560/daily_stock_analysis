import apiClient from './index';

export interface KeyMetrics {
  win_rate: number;
  profit_factor: number;
  direction_accuracy: number;
  total_records: number;
  closed_count: number;
}

export interface StopParams {
  hard_stop_pct: number;
  trailing_stop_pct: number;
  take_profit_target_pct: number;
  time_stop_days: number;
}

export interface HighRiskPosition {
  id: number;
  code: string;
  trade_date: string;
  signal: string;
  recommendation_price: number;
  current_price: number;
  deviation_pct: number;
}

export interface OptimizationReport {
  generated_at: string;
  health_score: number;
  health_level: string;
  key_metrics: KeyMetrics;
  source_weights: Record<string, number>;
  optimized_params: StopParams;
  issues: string[];
  suggestions: string[];
  high_risk_positions: HighRiskPosition[];
  error?: string;
}

export interface SourceWeightItem {
  source: string;
  weight: number;
  win_rate: number;
  total: number;
}

export interface DisciplineCheckRequest {
  code: string;
  bias_ma5?: number;
  volume_ratio?: number;
  ma_alignment?: string;
  concentration_90?: number;
  profit_ratio?: number;
}

export interface DisciplineCheckResponse {
  passed: boolean;
  violations: string[];
  rules: Record<string, number>;
}

export interface SignalFilterRequest {
  code: string;
  source: string;
  sentiment_score: number;
  bias_ma5?: number;
  volume_ratio?: number;
}

export interface SignalFilterResponse {
  filtered: boolean;
  reasons: string[];
  source_weight: number;
}

export async function getOptimizationReport(): Promise<OptimizationReport> {
  const response = await apiClient.get('/api/v1/strategy-optimizer/report');
  return response.data;
}

export async function getSourceWeights(): Promise<SourceWeightItem[]> {
  const response = await apiClient.get('/api/v1/strategy-optimizer/source-weights');
  return response.data;
}

export async function getOptimizedStopParams(): Promise<StopParams> {
  const response = await apiClient.get('/api/v1/strategy-optimizer/stop-params');
  return response.data;
}

export async function filterSignal(data: SignalFilterRequest): Promise<SignalFilterResponse> {
  const response = await apiClient.post('/api/v1/strategy-optimizer/filter-signal', data);
  return response.data;
}

export async function checkDiscipline(data: DisciplineCheckRequest): Promise<DisciplineCheckResponse> {
  const response = await apiClient.post('/api/v1/strategy-optimizer/check-discipline', data);
  return response.data;
}
