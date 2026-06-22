import { useCallback, useEffect, useMemo, useState } from 'react';
import { Badge, Select } from '@/components/common';
import { CheckCircle2, Cpu, Loader2, Radio, Sparkles } from 'lucide-react';
import { getParsedApiError } from '@/api/error';
import { systemConfigApi } from '@/api/systemConfig';
import type { ModelInfo } from '@/types/systemConfig';

export type DeepAnalysisModelSelection = {
  mode: 'inherit' | 'custom';
  model: string;
};

function buildModelNodes(currentModel: string, availableModels: ModelInfo[]): ModelInfo[] {
  const nodes = [...availableModels];
  if (currentModel && !nodes.some((item) => item.value === currentModel)) {
    nodes.unshift({
      value: currentModel,
      label: currentModel.replace(/^.*\//, ''),
      provider: 'current',
      status: 'active',
      tested: false,
      latencyMs: null,
    });
  }
  return nodes;
}

export function DeepAnalysisModelSelector({
  value,
  onChange,
}: {
  value: DeepAnalysisModelSelection;
  onChange: (next: DeepAnalysisModelSelection) => void;
}) {
  const [currentModel, setCurrentModel] = useState('');
  const [agentModel, setAgentModel] = useState('');
  const [availableModels, setAvailableModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [switchingModel, setSwitchingModel] = useState(false);
  const [switchMessage, setSwitchMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadModelStatus = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const status = await systemConfigApi.getModelStatus();
      setCurrentModel(status.currentModel || '');
      setAgentModel(status.agentModel || '');
      setAvailableModels(status.availableModels || []);

      if (status.currentModel && !value.model) {
        onChange({ ...value, model: status.currentModel });
      }
    } catch (error) {
      setLoadError(getParsedApiError(error).message || '加载模型状态失败');
      setAvailableModels([]);
      setCurrentModel('');
      setAgentModel('');
    } finally {
      setLoading(false);
    }
  }, [onChange, value]);

  useEffect(() => {
    void loadModelStatus();
  }, [loadModelStatus]);

  const modelNodes = useMemo(
    () => buildModelNodes(currentModel, availableModels),
    [availableModels, currentModel],
  );

  const providerGroups = useMemo(() => {
    const groups: Record<string, ModelInfo[]> = {};
    for (const node of modelNodes) {
      const key = node.provider || '其他';
      if (!groups[key]) groups[key] = [];
      groups[key].push(node);
    }
    return groups;
  }, [modelNodes]);

  const selectOptions = useMemo(
    () => {
      const options: { value: string; label: string }[] = [{ value: '', label: '选择模型...' }];
      const sortedProviders = Object.keys(providerGroups).sort((a, b) => {
        if (a === 'current') return -1;
        if (b === 'current') return 1;
        return a.localeCompare(b);
      });

      for (const provider of sortedProviders) {
        options.push({ value: `__sep_${provider}`, label: `── ${provider.toUpperCase()} ──` });
        for (const node of providerGroups[provider]) {
          const statusPrefix =
            node.status === 'active'
              ? '● '
              : node.tested && node.status === 'error'
                ? '✕ '
                : node.tested
                  ? '○ '
                  : '· ';
          const suffix = node.latencyMs ? `  (${node.latencyMs}ms)` : '';
          options.push({ value: node.value, label: `${statusPrefix}${node.label}${suffix}` });
        }
      }
      return options;
    },
    [providerGroups],
  );

  const selectedValue = value.mode === 'custom' ? value.model : currentModel;
  const currentNode = modelNodes.find((node) => node.value === selectedValue);
  const currentModelLabel = currentModel ? currentModel.replace(/^.*\//, '') : '当前未设置主模型';
  const currentProvider = currentModel.includes('/') ? currentModel.split('/')[0] : '';

  const handleSwitch = useCallback(
    async (modelValue: string) => {
      if (!modelValue || modelValue === currentModel) {
        onChange({ mode: 'inherit', model: currentModel });
        return;
      }

      setSwitchingModel(true);
      setSwitchMessage(null);
      try {
        // 仅更新本地选择，不修改全局 LITELLM_MODEL（避免影响其他功能）
        onChange({ mode: 'custom', model: modelValue });
        setSwitchMessage({ type: 'success', text: `已选择 ${modelValue.replace(/^.*\//, '')}` });
      } catch (error) {
        setSwitchMessage({
          type: 'error',
          text: getParsedApiError(error).message || '切换失败',
        });
      } finally {
        setSwitchingModel(false);
      }
    },
    [currentModel, onChange],
  );

  const currentSelection = value.mode === 'custom' ? value.model : currentModel;

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-subtle bg-base/60 px-3 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="relative flex-shrink-0">
              <Cpu className="h-4 w-4 text-primary" />
              {currentNode?.status === 'active' && (
                <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-success border border-base" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-foreground truncate">{currentModelLabel}</span>
                <Badge variant="success" className="text-[9px]">当前</Badge>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-text mt-0.5">
                {currentProvider && <span className="font-mono">{currentProvider}</span>}
                {currentNode?.tested && currentNode?.latencyMs != null && (
                  <span className="text-success flex items-center gap-0.5">
                    <CheckCircle2 className="h-2.5 w-2.5" />
                    {currentNode.latencyMs}ms
                  </span>
                )}
              </div>
            </div>
          </div>

          {switchMessage && (
            <span
              className={`flex-shrink-0 text-[10px] px-2 py-0.5 rounded-full ${
                switchMessage.type === 'success' ? 'bg-success/10 text-success' : 'bg-danger/10 text-danger'
              }`}
            >
              {switchMessage.text}
            </span>
          )}
        </div>
      </div>

      {agentModel && (
        <div className="flex items-center gap-2 px-1 text-[10px] text-muted-text">
          <Sparkles className="h-3 w-3 text-purple" />
          <span>Agent 模型:</span>
          <span className="font-mono text-secondary-text">{agentModel}</span>
        </div>
      )}

      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-secondary-text">切换模型</label>
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <Select
              value={currentSelection}
              onChange={(model) => {
                if (model && !model.startsWith('__sep_')) {
                  void handleSwitch(model);
                }
              }}
              options={selectOptions}
              disabled={switchingModel}
              placeholder="选择模型..."
              className="w-full"
            />
          </div>
          {switchingModel && <Loader2 className="h-4 w-4 animate-spin text-info flex-shrink-0" />}
        </div>

        <div className="flex flex-wrap gap-1 pt-1">
          {modelNodes.slice(0, 8).map((node) => (
            <button
              key={node.value}
              type="button"
              disabled={switchingModel || node.value === currentSelection}
              onClick={() => node.value !== currentSelection && void handleSwitch(node.value)}
              className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-mono transition-all cursor-pointer ${
                node.value === currentSelection
                  ? 'bg-primary/15 text-primary border border-primary/30 cursor-default'
                  : node.status === 'error'
                    ? 'bg-danger/5 text-danger border border-danger/20 hover:bg-danger/10'
                    : 'bg-surface text-secondary-text border border-subtle hover:border-subtle-hover hover:text-foreground'
              } disabled:opacity-40 disabled:cursor-not-allowed`}
              title={`${node.value}${node.latencyMs ? ` (${node.latencyMs}ms)` : ''}`}
            >
              {node.value === currentSelection && <Radio className="h-2.5 w-2.5" />}
              {node.label}
            </button>
          ))}
          {modelNodes.length > 8 && <span className="px-1.5 py-1 text-[10px] text-muted-text">+{modelNodes.length - 8} more</span>}
        </div>

        {loadError && <div className="text-[10px] text-danger">{loadError}</div>}
        {!loadError && currentSelection && currentSelection === currentModel && !loading && (
          <div className="text-[10px] text-success">当前选择已生效</div>
        )}
      </div>
    </div>
  );
}
