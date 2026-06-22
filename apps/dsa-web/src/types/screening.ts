/**
 * Screening API type definitions for AlphaSift and factor pipeline actions.
 */

export interface FactorPipelineSeriesSpec {
  name: string;
  window: number;
  provider?: string;
}

export interface FactorPipelineFactorFamily {
  alpha158?: FactorPipelineSeriesSpec[];
  alpha360?: FactorPipelineSeriesSpec[];
}

export interface FactorPipelineTrainingSummary {
  algorithm?: string;
  rolling?: boolean;
  enabled?: boolean;
  shap_enabled?: boolean;
  ic_ir_monitoring_enabled?: boolean;
  sample_size?: number;
  status?: string;
  backend?: string;
}

export interface FactorPipelineMonitoringSummary {
  ic?: number | null;
  ir?: number | null;
  decay?: number | null;
  decay_alert?: boolean;
  sample_size?: number;
  backend?: string;
}

export interface FactorPipelineTraceDetails {
  train_window_days?: number;
  valid_window_days?: number;
  test_window_days?: number;
  shap_sample_size?: number;
  backend_error?: string | null;
}

export interface FactorPipelineTraceItem {
  code?: string;
  backend?: string;
  train_window_days?: number;
  valid_window_days?: number;
  test_window_days?: number;
  shap_sample_size?: number;
  backend_error?: string | null;
}

export interface FactorPipelineTraces {
  backend?: string;
  runtime_window?: {
    train_days?: number;
    valid_days?: number;
    test_days?: number;
    shap_sample_size?: number;
  };
  candidate_traces?: FactorPipelineTraceItem[];
  backends_seen?: string[];
}

export interface FactorPipelineFeatureImpact {
  name?: string;
  impact?: number;
}

export interface FactorPipelineInterpretation {
  shap_enabled?: boolean;
  top_features?: FactorPipelineFeatureImpact[];
  score?: number;
}

export interface FactorPipelineCandidate {
  candidate_id?: number;
  code?: string;
  name?: string;
  rank?: number;
  base_score?: number;
  factor_scores?: Record<string, number>;
  factor_score?: number;
  backend?: string;
  model?: Record<string, unknown>;
  training?: FactorPipelineTrainingSummary;
  monitoring?: FactorPipelineMonitoringSummary;
  traces?: FactorPipelineTraceDetails;
  interpretation?: FactorPipelineInterpretation;
}

export interface FactorPipelineSummary {
  status?: string;
  backend?: string;
  factorPipelineEnabled?: boolean;
  candidateCount?: number;
  training?: FactorPipelineTrainingSummary;
  monitoring?: FactorPipelineMonitoringSummary;
  topCandidates?: FactorPipelineCandidate[];
  latestRecordId?: number | null;
  latestStrategy?: string | null;
  latestScreeningDate?: string | null;
  factorFamily?: FactorPipelineFactorFamily;
}

export interface FactorPipelineRecordResponse {
  recordId: number;
  factorPipeline: FactorPipelineSummary;
}

export interface FactorPipelineTriggerRequest {
  recordId: number;
  market?: string;
  screeningDate?: string;
}

export interface FactorPipelineTriggerResponse {
  status: string;
  recordId: number;
  factorPipelineEnabled: boolean;
  screeningDate?: string | null;
  market?: string | null;
  backend?: string | null;
  factorFamily?: FactorPipelineFactorFamily | null;
  training?: FactorPipelineTrainingSummary | null;
  monitoring?: FactorPipelineMonitoringSummary | null;
  traces?: FactorPipelineTraces | null;
  candidates?: FactorPipelineCandidate[] | null;
  error?: string | null;
}
