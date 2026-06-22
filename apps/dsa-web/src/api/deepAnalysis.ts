import apiClient from './index';

export interface PipelineStage {
  id: string;
  name: string;
  icon: string;
}

export interface RunAnalysisRequest {
  ticker: string;
  trade_date: string;
  base_url?: string;
  model?: string;
}

export interface TaskStatus {
  task_id: string;
  ticker: string;
  trade_date: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  signal: string;
  current_stage: string;
  completed_stages: string[];
  stage_reports: Record<string, string>;
  stats: { llm_calls: number; tool_calls: number; tokens_in: number; tokens_out: number };
  elapsed: number;
  error: string;
  report_path: string;
  report_download_url: string;
}

export const deepAnalysisApi = {
  /** 获取流水线阶段定义 */
  getPipelineStages: () =>
    apiClient.get<PipelineStage[]>('/api/v1/deep-analysis/stages').then(res => res.data),

  /** 启动分析任务 */
  startAnalysis: (payload: RunAnalysisRequest) =>
    apiClient.post<{ task_id: string; status: string }>('/api/v1/deep-analysis/run', payload).then(res => res.data),

  /** 查询任务状态 */
  getTaskStatus: (taskId: string) =>
    apiClient.get<TaskStatus>(`/api/v1/deep-analysis/tasks/${taskId}`).then(res => res.data),

  /** 列出所有任务 */
  listTasks: () =>
    apiClient.get<TaskStatus[]>('/api/v1/deep-analysis/tasks').then(res => res.data),

  /** 删除任务 */
  deleteTask: (taskId: string) =>
    apiClient.delete<{ message: string; task_id: string }>(`/api/v1/deep-analysis/tasks/${taskId}`).then(res => res.data),

  /** 获取报告内容（Markdown 文本） */
  getReportContent: (taskId: string) =>
    apiClient.get<{ content: string; filename: string }>(`/api/v1/deep-analysis/tasks/${taskId}/report`).then(res => res.data),

  /** 下载报告 */
  getReportDownloadUrl: (taskId: string) =>
    `/api/v1/deep-analysis/tasks/${taskId}/report/download`,
};
