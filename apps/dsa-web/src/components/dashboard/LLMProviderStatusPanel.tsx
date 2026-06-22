import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Cpu,
  Loader2,
  Radio,
  Sparkles,
  Wifi,
  WifiOff,
  XCircle,
  Zap,
} from 'lucide-react';
import { systemConfigApi } from '../../api/systemConfig';
import { getParsedApiError } from '../../api/error';
import type {
  DiscoverLLMChannelModelsResponse,
  ModelInfo,
  SystemConfigItem,
  TestLLMChannelResponse,
} from '../../types/systemConfig';
import { Badge, Button, Select, StatusDot } from '../common';

// ============================================================
// Types
// ============================================================

interface LLMChannelInfo {
  name: string;
  protocol: string;
  baseUrl: string;
  apiKeyMasked: string;
  models: string[];
  enabled: boolean;
}

type TestStatus = 'idle' | 'testing' | 'success' | 'error';

interface ChannelTestResult {
  status: TestStatus;
  message?: string;
  latencyMs?: number;
  resolvedModel?: string;
  errorCode?: string;
}

interface ProviderState {
  channel: LLMChannelInfo;
  testResult: ChannelTestResult;
  discoveredModels: string[];
  discoveryStatus: 'idle' | 'loading' | 'done' | 'error';
  expanded: boolean;
}

interface ModelNode extends ModelInfo {
  providerName: string;
  protocol: string;
}

// ============================================================
// Helpers
// ============================================================

const LLM_CHANNEL_KEY_RE = /^LLM_([A-Z][A-Z0-9_]*?)_(API_KEY|API_KEYS|BASE_URL|MODELS|PROTOCOL|ENABLED|EXTRA_HEADERS)$/;
const NON_CHANNEL_PREFIXES = new Set(['TA', 'DEEPSEEK']);

function maskKey(key: string): string {
  if (!key) return '';
  if (key.length <= 8) return '****';
  return key.slice(0, 4) + '****' + key.slice(-4);
}

function parseChannelsFromConfig(items: SystemConfigItem[]): LLMChannelInfo[] {
  const itemMap = new Map(items.map((item) => [item.key, item.value]));
  const channelNamesStr = (itemMap.get('LLM_CHANNELS') || '')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean);

  const discoveredProviders = new Map<
    string,
    { apiKey: string; baseUrl: string; models: string; protocol: string; enabled: string }
  >();

  for (const [key, value] of itemMap) {
    const match = key.match(LLM_CHANNEL_KEY_RE);
    if (!match) continue;
    const channelName = match[1];
    const field = match[2];
    if (NON_CHANNEL_PREFIXES.has(channelName)) continue;

    if (!discoveredProviders.has(channelName)) {
      discoveredProviders.set(channelName, {
        apiKey: '',
        baseUrl: '',
        models: '',
        protocol: '',
        enabled: '',
      });
    }
    const entry = discoveredProviders.get(channelName)!;
    if (field === 'API_KEY' || field === 'API_KEYS') entry.apiKey = value;
    else if (field === 'BASE_URL') entry.baseUrl = value;
    else if (field === 'MODELS') entry.models = value;
    else if (field === 'PROTOCOL') entry.protocol = value;
    else if (field === 'ENABLED') entry.enabled = value;
  }

  const channels: LLMChannelInfo[] = [];
  const addedNames = new Set<string>();

  for (const name of channelNamesStr) {
    const cfg = discoveredProviders.get(name);
    const rawModels = cfg?.models || itemMap.get(`LLM_${name}_MODELS`) || '';
    const enabled =
      (cfg?.enabled || itemMap.get(`LLM_${name}_ENABLED`) || 'true').toLowerCase() !== 'false';
    const apiKey =
      cfg?.apiKey ||
      itemMap.get(`LLM_${name}_API_KEYS`) ||
      itemMap.get(`LLM_${name}_API_KEY`) ||
      '';

    channels.push({
      name: name.toLowerCase(),
      protocol: cfg?.protocol || itemMap.get(`LLM_${name}_PROTOCOL`) || 'openai',
      baseUrl: cfg?.baseUrl || itemMap.get(`LLM_${name}_BASE_URL`) || '',
      apiKeyMasked: maskKey(apiKey),
      models: rawModels
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      enabled,
    });
    addedNames.add(name);
  }

  for (const [name, cfg] of discoveredProviders) {
    if (addedNames.has(name)) continue;
    if (!cfg.apiKey && !cfg.baseUrl && !cfg.models) continue;

    channels.push({
      name: name.toLowerCase(),
      protocol: cfg.protocol || 'openai',
      baseUrl: cfg.baseUrl || '',
      apiKeyMasked: maskKey(cfg.apiKey),
      models: cfg.models
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean),
      enabled: false,
    });
  }

  if (channels.length === 0) {
    const baseUrl = itemMap.get('OPENAI_BASE_URL') || '';
    const apiKey = itemMap.get('OPENAI_API_KEY') || itemMap.get('AGNES_API_KEY') || '';
    const model = itemMap.get('LITELLM_MODEL') || '';
    const modelName = model.includes('/') ? model.split('/').slice(1).join('/') : model;
    const provider = baseUrl ? new URL(baseUrl).hostname : 'Unknown';

    if (apiKey || modelName) {
      channels.push({
        name: provider.replace('api.', '').split('.')[0],
        protocol: 'openai',
        baseUrl,
        apiKeyMasked: maskKey(apiKey),
        models: modelName ? [model] : [],
        enabled: true,
      });
    }
  }

  return channels;
}

function buildModelNodes(
  channels: LLMChannelInfo[],
  currentModel: string,
  testResults: Record<string, ChannelTestResult | undefined>,
): ModelNode[] {
  const nodes: ModelNode[] = [];
  const seen = new Set<string>();

  for (const ch of channels) {
    const provider = ch.name;
    const protocol = ch.protocol;
    const chTest = testResults[ch.name];

    for (const model of ch.models) {
      const value = model.includes('/') ? model : `${protocol}/${model}`;
      if (seen.has(value)) continue;
      seen.add(value);

      const isCurrent = value === currentModel;
      let status: ModelInfo['status'] = 'available';
      if (isCurrent) {
        status = 'active';
      } else if (chTest?.status === 'success') {
        status = 'available';
      } else if (chTest?.status === 'error') {
        status = 'error';
      }

      nodes.push({
        value,
        label: model.replace(/^.*\//, ''),
        provider,
        providerName: provider,
        protocol,
        status,
        latencyMs: chTest?.latencyMs ?? null,
        tested: chTest?.status === 'success' || chTest?.status === 'error',
      });
    }
  }

  // Add current model if not in list
  if (currentModel && !seen.has(currentModel)) {
    nodes.unshift({
      value: currentModel,
      label: currentModel.replace(/^.*\//, ''),
      provider: 'current',
      providerName: 'current',
      protocol: 'openai',
      status: 'active',
      latencyMs: null,
      tested: false,
    });
  }

  return nodes;
}

function extractCurrentModel(items: SystemConfigItem[]): string {
  return new Map(items.map((item) => [item.key, item.value])).get('LITELLM_MODEL') || '';
}

function extractAgentModel(items: SystemConfigItem[]): string {
  return new Map(items.map((item) => [item.key, item.value])).get('AGENT_LITELLM_MODEL') || '';
}

// ============================================================
// Sub-component: ModelSwitcherCard
// ============================================================

const ModelSwitcherCard: React.FC<{
  currentModel: string;
  agentModel: string;
  modelNodes: ModelNode[];
  switchingModel: boolean;
  switchMessage: { type: 'success' | 'error'; text: string } | null;
  onSwitch: (modelValue: string) => void;
}> = ({ currentModel, agentModel, modelNodes, switchingModel, switchMessage, onSwitch }) => {
  const currentModelLabel = currentModel ? currentModel.replace(/^.*\//, '') : '未设置';
  const currentProvider = currentModel.includes('/')
    ? currentModel.split('/')[0]
    : '';

  // Group models by provider for grouped dropdown
  const providerGroups = useMemo(() => {
    const groups: Record<string, ModelNode[]> = {};
    for (const node of modelNodes) {
      const key = node.providerName || node.provider;
      if (!groups[key]) groups[key] = [];
      groups[key].push(node);
    }
    return groups;
  }, [modelNodes]);

  // Build aggregated select options
  const selectOptions = useMemo(() => {
    const opts: { value: string; label: string }[] = [
      { value: '', label: '选择模型...' },
    ];
    const sortedKeys = Object.keys(providerGroups).sort((a, b) => {
      if (a === 'current') return -1;
      if (b === 'current') return 1;
      return a.localeCompare(b);
    });

    // Track current model position for optgroup-style labels
    for (const provider of sortedKeys) {
      const group = providerGroups[provider];
      // Use separator labels with prefix
      opts.push({
        value: `__sep_${provider}`,
        label: `── ${provider.toUpperCase()} ──`,
      });

      for (const node of group) {
        const statusPrefix =
          node.status === 'active'
            ? '● '
            : node.tested && node.status === 'error'
              ? '✕ '
              : node.tested
                ? '○ '
                : '· ';
        const suffix = node.latencyMs ? `  (${node.latencyMs}ms)` : '';
        opts.push({
          value: node.value,
          label: `${statusPrefix}${node.label}${suffix}`,
        });
      }
    }
    return opts;
  }, [providerGroups]);

  const selectedNode = modelNodes.find((n) => n.value === currentModel);

  return (
    <div className="space-y-3">
      {/* Current model status card */}
      <div className="rounded-lg border border-subtle bg-base/60 px-3 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="relative flex-shrink-0">
              <Cpu className="h-4 w-4 text-primary" />
              {selectedNode?.status === 'active' && (
                <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-success border border-base" />
              )}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-foreground truncate">
                  {currentModelLabel}
                </span>
                <Badge variant="success" className="text-[9px]">当前</Badge>
              </div>
              <div className="flex items-center gap-1.5 text-[10px] text-muted-text mt-0.5">
                {currentProvider && (
                  <span className="font-mono">{currentProvider}</span>
                )}
                {selectedNode?.tested && selectedNode?.latencyMs && (
                  <span className="text-success flex items-center gap-0.5">
                    <CheckCircle2 className="h-2.5 w-2.5" />
                    {selectedNode.latencyMs}ms
                  </span>
                )}
              </div>
            </div>
          </div>

          {switchMessage && (
            <span
              className={`flex-shrink-0 text-[10px] px-2 py-0.5 rounded-full ${
                switchMessage.type === 'success'
                  ? 'bg-success/10 text-success'
                  : 'bg-danger/10 text-danger'
              }`}
            >
              {switchMessage.text}
            </span>
          )}
        </div>
      </div>

      {/* Agent model info */}
      {agentModel && (
        <div className="flex items-center gap-2 text-[10px] text-muted-text px-1">
          <Sparkles className="h-3 w-3 text-purple" />
          <span>Agent 模型:</span>
          <span className="font-mono text-secondary-text">{agentModel}</span>
        </div>
      )}

      {/* Model switch dropdown */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-medium text-secondary-text">
          切换模型
        </label>
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <Select
              value={currentModel}
              onChange={(v) => {
                if (v && !v.startsWith('__sep_')) onSwitch(v);
              }}
              options={selectOptions}
              disabled={switchingModel}
              placeholder="选择要切换的模型..."
              className="w-full"
            />
          </div>
          {switchingModel && (
            <Loader2 className="h-4 w-4 animate-spin text-info flex-shrink-0" />
          )}
        </div>

        {/* Model quick chips */}
        {modelNodes.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {modelNodes.slice(0, 8).map((node) => (
              <button
                key={node.value}
                type="button"
                disabled={switchingModel || node.value === currentModel}
                onClick={() => node.value !== currentModel && onSwitch(node.value)}
                className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] font-mono transition-all cursor-pointer ${
                  node.value === currentModel
                    ? 'bg-primary/15 text-primary border border-primary/30 cursor-default'
                    : node.status === 'error'
                      ? 'bg-danger/5 text-danger border border-danger/20 hover:bg-danger/10'
                      : 'bg-surface text-secondary-text border border-subtle hover:border-subtle-hover hover:text-foreground'
                } disabled:opacity-40 disabled:cursor-not-allowed`}
                title={`${node.value}${node.latencyMs ? ` (${node.latencyMs}ms)` : ''}`}
              >
                {node.value === currentModel && <Radio className="h-2.5 w-2.5" />}
                {node.label}
              </button>
            ))}
            {modelNodes.length > 8 && (
              <span className="text-[10px] text-muted-text px-1.5 py-1">
                +{modelNodes.length - 8} more
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// ============================================================
// Main Component
// ============================================================

const LLMProviderStatusPanel: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [configItems, setConfigItems] = useState<SystemConfigItem[]>([]);
  const [currentModel, setCurrentModel] = useState('');
  const [agentModel, setAgentModel] = useState('');
  const [providerStates, setProviderStates] = useState<Record<string, ProviderState>>({});
  const [switchingModel, setSwitchingModel] = useState(false);
  const [switchMessage, setSwitchMessage] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const testAbortRef = useRef<Record<string, AbortController>>({});
  const switchTimerRef = useRef<number | null>(null);
  const autoTestDoneRef = useRef(false);

  // ── Helpers ──
  const configValueMap = useMemo(
    () => new Map(configItems.map((item) => [item.key, item.value])),
    [configItems],
  );

  // ── Load config ──
  const loadConfig = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const configRes = await systemConfigApi.getConfig(false);
      setConfigItems(configRes.items);
      setCurrentModel(extractCurrentModel(configRes.items));
      setAgentModel(extractAgentModel(configRes.items));
    } catch (err) {
      setLoadError(getParsedApiError(err).message || '加载配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  // ── Parse channels and model nodes ──
  const channels = useMemo(() => parseChannelsFromConfig(configItems), [configItems]);

  // Collect test results for model nodes
  const channelTestResults = useMemo(() => {
    const results: Record<string, ChannelTestResult> = {};
    for (const [name, state] of Object.entries(providerStates)) {
      results[name] = state.testResult;
    }
    return results;
  }, [providerStates]);

  const modelNodes = useMemo(
    () => buildModelNodes(channels, currentModel, channelTestResults),
    [channels, currentModel, channelTestResults],
  );

  // ── Initialize provider states ──
  useEffect(() => {
    setProviderStates((prev) => {
      const next: Record<string, ProviderState> = {};
      for (const ch of channels) {
        const key = ch.name;
        next[key] = prev[key] || {
          channel: ch,
          testResult: { status: 'idle' },
          discoveredModels: [],
          discoveryStatus: 'idle',
          expanded: false,
        };
        next[key] = {
          ...next[key],
          channel: ch,
        };
      }
      return next;
    });
  }, [channels]);

  // ── Test connectivity ──
  const testChannel = useCallback(
    async (channel: LLMChannelInfo) => {
      const key = channel.name;
      testAbortRef.current[key]?.abort();

      setProviderStates((prev) => ({
        ...prev,
        [key]: { ...prev[key], testResult: { status: 'testing' } },
      }));

      try {
        const upper = channel.name.toUpperCase();
        const actualKey =
          configValueMap.get(`LLM_${upper}_API_KEYS`) ||
          configValueMap.get(`LLM_${upper}_API_KEY`) ||
          '';
        const result: TestLLMChannelResponse = await systemConfigApi.testLLMChannel({
          name: channel.name,
          protocol: channel.protocol,
          baseUrl: channel.baseUrl,
          apiKey: actualKey,
          models: channel.models,
          enabled: channel.enabled,
          timeoutSeconds: 10,
        });

        setProviderStates((prev) => ({
          ...prev,
          [key]: {
            ...prev[key],
            testResult: {
              status: result.success ? 'success' : 'error',
              message: result.message,
              latencyMs: result.latencyMs ?? undefined,
              resolvedModel: result.resolvedModel ?? undefined,
              errorCode: result.errorCode ?? undefined,
            },
          },
        }));
      } catch (err) {
        const parsed = getParsedApiError(err);
        setProviderStates((prev) => ({
          ...prev,
          [key]: {
            ...prev[key],
            testResult: {
              status: 'error',
              message: parsed.message || '测试失败',
              errorCode: 'network_error',
            },
          },
        }));
      }
    },
    [configValueMap],
  );

  // ── Discover models ──
  const discoverModels = useCallback(async (channel: LLMChannelInfo) => {
    const key = channel.name;
    setProviderStates((prev) => ({
      ...prev,
      [key]: { ...prev[key], discoveryStatus: 'loading' },
    }));

    try {
      const upper = channel.name.toUpperCase();
      const actualKey =
        configValueMap.get(`LLM_${upper}_API_KEYS`) ||
        configValueMap.get(`LLM_${upper}_API_KEY`) ||
        '';
      const result: DiscoverLLMChannelModelsResponse =
        await systemConfigApi.discoverLLMChannelModels({
          name: channel.name,
          protocol: channel.protocol,
          baseUrl: channel.baseUrl,
          apiKey: actualKey,
          models: channel.models,
          timeoutSeconds: 10,
        });

      setProviderStates((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          discoveryStatus: result.success ? 'done' : 'error',
          discoveredModels: result.success
            ? result.models
            : prev[key].discoveredModels,
        },
      }));
    } catch {
      setProviderStates((prev) => ({
        ...prev,
        [key]: {
          ...prev[key],
          discoveryStatus: 'error',
        },
      }));
    }
  }, []);

  // ── Switch model ──
  const handleSwitchModel = useCallback(
    async (modelValue: string) => {
      if (!modelValue || modelValue === currentModel) return;
      setSwitchingModel(true);
      setSwitchMessage(null);

      try {
        const config = await systemConfigApi.getConfig(false);
        await systemConfigApi.update({
          configVersion: config.configVersion,
          maskToken: config.maskToken,
          reloadNow: true,
          items: [{ key: 'LITELLM_MODEL', value: modelValue }],
        });
        setCurrentModel(modelValue);
        setSwitchMessage({ type: 'success', text: `已切换到 ${modelValue.replace(/^.*\//, '')}` });

        if (switchTimerRef.current) window.clearTimeout(switchTimerRef.current);
        switchTimerRef.current = window.setTimeout(() => setSwitchMessage(null), 4000);
      } catch (err) {
        setSwitchMessage({
          type: 'error',
          text: getParsedApiError(err).message || '切换失败',
        });
      } finally {
        setSwitchingModel(false);
      }
    },
    [currentModel],
  );

  useEffect(() => {
    return () => {
      if (switchTimerRef.current) window.clearTimeout(switchTimerRef.current);
    };
  }, []);

  // ── Auto-test channels on first load ──
  useEffect(() => {
    if (autoTestDoneRef.current || channels.length === 0) return;
    autoTestDoneRef.current = true;

    // Test enabled channels with a slight stagger to avoid overwhelming
    const enabledChannels = channels.filter((ch) => ch.enabled);
    enabledChannels.forEach((ch, i) => {
      setTimeout(() => {
        void testChannel(ch);
      }, i * 400);
    });
  }, [channels, testChannel]);

  // ── Test all channels ──
  const testAllChannels = useCallback(() => {
    for (const ch of channels) {
      if (ch.enabled) void testChannel(ch);
    }
  }, [channels, testChannel]);

  // ── Aggregate status ──
  const overallStatus = useMemo(() => {
    const states = Object.values(providerStates);
    const enabledStates = states.filter((s) => s.channel.enabled);
    if (enabledStates.length === 0) return 'unknown';
    const hasError = enabledStates.some((s) => s.testResult.status === 'error');
    const hasSuccess = enabledStates.some((s) => s.testResult.status === 'success');
    const hasTesting = enabledStates.some((s) => s.testResult.status === 'testing');

    if (hasTesting) return 'testing';
    if (hasError && !hasSuccess) return 'error';
    if (hasSuccess && hasError) return 'partial';
    if (hasSuccess) return 'connected';
    return 'unknown';
  }, [providerStates]);

  const statusIcon = useMemo(() => {
    switch (overallStatus) {
      case 'connected':
        return <Wifi className="h-4 w-4 text-success" />;
      case 'error':
        return <WifiOff className="h-4 w-4 text-danger" />;
      case 'partial':
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case 'testing':
        return <Loader2 className="h-4 w-4 animate-spin text-info" />;
      default:
        return <Activity className="h-4 w-4 text-muted-text" />;
    }
  }, [overallStatus]);

  const statusLabel = useMemo(() => {
    switch (overallStatus) {
      case 'connected':
        return 'LLM 已连接';
      case 'error':
        return 'LLM 连接失败';
      case 'partial':
        return '部分连接异常';
      case 'testing':
        return '测试中...';
      default:
        return '未检测';
    }
  }, [overallStatus]);

  const statusBadgeVariant = useMemo(() => {
    switch (overallStatus) {
      case 'connected':
        return 'success' as const;
      case 'error':
        return 'danger' as const;
      case 'partial':
        return 'warning' as const;
      case 'testing':
        return 'info' as const;
      default:
        return 'default' as const;
    }
  }, [overallStatus]);

  // ── Render ──
  if (loading) {
    return (
      <div className="mb-3 rounded-xl border border-subtle bg-surface/70 px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs text-muted-text">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          加载 LLM 配置...
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="mb-3 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5">
        <div className="flex items-center gap-2 text-xs text-danger">
          <XCircle className="h-3.5 w-3.5" />
          LLM 配置加载失败: {loadError}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void loadConfig()}
            className="ml-2 h-6 px-2 text-xs"
          >
            重试
          </Button>
        </div>
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <div className="mb-3 rounded-xl border border-warning/30 bg-warning/5 px-4 py-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            未配置 LLM 提供商，请前往设置页配置
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => (window.location.href = '/settings')}
            className="h-7 px-3 text-xs"
          >
            去配置
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-3 rounded-xl border border-subtle bg-surface/70 shadow-sm transition-all">
      {/* ── Header bar: always visible, includes inline model switcher ── */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-2 px-4 py-2.5">
        {/* Left: status + toggle */}
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center gap-2.5 text-left hover:opacity-80 transition-opacity flex-shrink-0"
        >
          {statusIcon}
          <Badge variant={statusBadgeVariant} className="text-[10px]">
            {statusLabel}
          </Badge>
        </button>

        {/* Center: current model info */}
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="flex items-center gap-1.5 min-w-0">
            <Cpu className="h-3 w-3 text-muted-text flex-shrink-0" />
            {currentModel ? (
              <span className="text-xs font-mono text-foreground truncate">
                {currentModel.replace(/^.*\//, '')}
              </span>
            ) : (
              <span className="text-xs text-muted-text">当前未设置主模型</span>
            )}
            <StatusDot
              tone={
                overallStatus === 'connected'
                  ? 'success'
                  : overallStatus === 'error'
                    ? 'danger'
                    : overallStatus === 'testing'
                      ? 'warning'
                      : 'neutral'
              }
              pulse={overallStatus === 'testing'}
            />
          </div>
          {agentModel && (
            <span className="hidden sm:inline text-[10px] text-muted-text font-mono">
              <Sparkles className="inline h-2.5 w-2.5 mr-0.5 text-purple" />
              Agent: {agentModel.replace(/^.*\//, '')}
            </span>
          )}
        </div>

        {/* Right: channel count + expand */}
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="flex items-center gap-2 flex-shrink-0 hover:opacity-80 transition-opacity"
        >
          {switchMessage && (
            <span
              className={`hidden sm:inline text-[10px] animate-in fade-in slide-in-from-right-2 duration-150 ${
                switchMessage.type === 'success' ? 'text-success' : 'text-danger'
              }`}
            >
              {switchMessage.text}
            </span>
          )}
          <span className="text-[10px] text-muted-text whitespace-nowrap">
            {channels.filter((c) => c.enabled).length}/{channels.length} 提供商
          </span>
          <ChevronDown
            className={`h-3.5 w-3.5 text-muted-text transition-transform ${
              collapsed ? '' : 'rotate-180'
            }`}
          />
        </button>
      </div>

      {/* Mobile switch feedback */}
      {switchMessage && (
        <div
          className={`sm:hidden mx-4 mb-2 text-[10px] px-2.5 py-1 rounded-md animate-in fade-in slide-in-from-top-1 duration-150 ${
            switchMessage.type === 'success'
              ? 'bg-success/10 text-success border border-success/20'
              : 'bg-danger/10 text-danger border border-danger/20'
          }`}
        >
          {switchMessage.text}
        </div>
      )}

      {/* ── Expanded panel ── */}
      {!collapsed && (
        <div className="border-t border-subtle px-4 py-3 space-y-5 animate-in fade-in slide-in-from-top-1 duration-200">
          {/* Model switcher card */}
          <ModelSwitcherCard
            currentModel={currentModel}
            agentModel={agentModel}
            modelNodes={modelNodes}
            switchingModel={switchingModel}
            switchMessage={switchMessage}
            onSwitch={(v) => {
              void handleSwitchModel(v);
            }}
          />

          {/* Divider */}
          <div className="border-t border-subtle" />

          {/* Quick test section */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-secondary-text">
                提供商状态与测试
              </span>
              <Button
                variant="secondary"
                size="sm"
                className="h-7 px-2.5 text-[10px]"
                onClick={testAllChannels}
                disabled={Object.values(providerStates).some(
                  (s) => s.testResult.status === 'testing',
                )}
              >
                {Object.values(providerStates).some(
                  (s) => s.testResult.status === 'testing',
                ) ? (
                  <>
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    检测中
                  </>
                ) : (
                  <>
                    <Zap className="mr-1 h-3 w-3" />
                    检测全部
                  </>
                )}
              </Button>
            </div>

            {/* Provider list */}
            <div className="space-y-1.5">
              {channels.map((ch) => {
                const state = providerStates[ch.name];
                const tr = state?.testResult;
                const isExpanded = state?.expanded ?? false;

                return (
                  <div
                    key={ch.name}
                    className={`rounded-lg border transition-all ${
                      !ch.enabled
                        ? 'border-subtle bg-base/50 opacity-60'
                        : tr?.status === 'success'
                          ? 'border-success/20 bg-success/5'
                          : tr?.status === 'error'
                            ? 'border-danger/20 bg-danger/5'
                            : tr?.status === 'testing'
                              ? 'border-info/20 bg-info/5'
                              : 'border-subtle bg-base/50'
                    }`}
                  >
                    {/* Provider row */}
                    <div
                      className="flex items-center gap-2.5 px-3 py-2 cursor-pointer select-none"
                      onClick={() => {
                        setProviderStates((prev) => ({
                          ...prev,
                          [ch.name]: {
                            ...prev[ch.name],
                            expanded: !isExpanded,
                          },
                        }));
                      }}
                    >
                      <StatusDot
                        tone={
                          !ch.enabled
                            ? 'neutral'
                            : tr?.status === 'success'
                              ? 'success'
                              : tr?.status === 'error'
                                ? 'danger'
                                : tr?.status === 'testing'
                                  ? 'warning'
                                  : 'neutral'
                        }
                        pulse={tr?.status === 'testing'}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-medium text-foreground truncate">
                            {ch.name}
                          </span>
                          <Badge variant="info" className="text-[9px]">
                            {ch.protocol}
                          </Badge>
                          {!ch.enabled && (
                            <Badge variant="default" className="text-[9px]">
                              仅展示
                            </Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-muted-text mt-0.5">
                          {tr?.status === 'success' && (
                            <span className="text-success">
                              <CheckCircle2 className="inline h-3 w-3 mr-0.5" />
                              {tr.latencyMs ? `${tr.latencyMs}ms` : '连通'}
                            </span>
                          )}
                          {tr?.status === 'error' && (
                            <span className="text-danger" title={tr.message}>
                              <XCircle className="inline h-3 w-3 mr-0.5" />
                              {tr.errorCode || '失败'}
                            </span>
                          )}
                          {tr?.status === 'idle' && <span>待检测</span>}
                          {tr?.status === 'testing' && (
                            <span className="text-info">检测中...</span>
                          )}
                          <span>{ch.models.length} 个模型</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1 flex-shrink-0">
                        {ch.enabled && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-1.5 text-[10px]"
                              disabled={tr?.status === 'testing'}
                              onClick={(e) => {
                                e.stopPropagation();
                                void testChannel(ch);
                              }}
                            >
                              {tr?.status === 'testing' ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                '测试'
                              )}
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-1.5 text-[10px]"
                              disabled={state?.discoveryStatus === 'loading'}
                              onClick={(e) => {
                                e.stopPropagation();
                                void discoverModels(ch);
                              }}
                            >
                              获取模型
                            </Button>
                          </>
                        )}
                        <ChevronDown
                          className={`h-3 w-3 text-muted-text transition-transform ${
                            isExpanded ? 'rotate-180' : ''
                          }`}
                        />
                      </div>
                    </div>

                    {/* Expanded details */}
                    {isExpanded && (
                      <div className="border-t border-subtle px-3 py-2.5 space-y-2 text-[11px] animate-in fade-in slide-in-from-top-1 duration-150">
                        {/* Connection details */}
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                          <span className="text-muted-text">协议</span>
                          <span className="text-foreground font-mono">
                            {ch.protocol}
                          </span>
                          <span className="text-muted-text">Base URL</span>
                          <span className="text-foreground font-mono truncate">
                            {ch.baseUrl || '(默认)'}
                          </span>
                          <span className="text-muted-text">API Key</span>
                          <span className="text-foreground font-mono">
                            {ch.apiKeyMasked || '(未设置)'}
                          </span>
                        </div>

                        {/* Models */}
                        <div>
                          <span className="text-muted-text">可切换模型</span>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {ch.models.map((m) => (
                              <span
                                key={m}
                                className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-mono cursor-pointer transition-colors ${
                                  m === currentModel ||
                                  currentModel.endsWith(m) ||
                                  currentModel.includes(m)
                                    ? 'bg-primary/15 text-primary border border-primary/30'
                                    : 'bg-surface text-secondary-text border border-subtle hover:border-subtle-hover'
                                }`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void handleSwitchModel(m);
                                }}
                              >
                                {(m === currentModel ||
                                  currentModel.endsWith(m) ||
                                  currentModel.includes(m)) && (
                                  <Radio className="h-2.5 w-2.5 mr-1" />
                                )}
                                {m.replace(/^.*\//, '')}
                              </span>
                            ))}
                          </div>
                        </div>

                        {/* Discovered models */}
                        {state?.discoveredModels.length > 0 && (
                          <div>
                            <span className="text-muted-text">
                              发现的模型 ({state.discoveredModels.length})
                            </span>
                            <div className="mt-1 flex flex-wrap gap-1 max-h-24 overflow-y-auto">
                              {state.discoveredModels.map((m) => (
                                <span
                                  key={m}
                                  className="inline-flex items-center rounded-md bg-surface px-1.5 py-0.5 text-[10px] font-mono text-secondary-text border border-subtle"
                                >
                                  {m}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Test result details */}
                        {tr?.status === 'error' && tr.message && (
                          <div className="rounded-md bg-danger/5 border border-danger/20 px-2 py-1.5">
                            <span className="text-danger text-[10px]">
                              {tr.message}
                            </span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick action: go to settings */}
          <div className="pt-1">
            <Button
              variant="ghost"
              size="sm"
              className="w-full h-8 text-[11px] text-muted-text"
              onClick={() => (window.location.href = '/settings')}
            >
              在设置页管理 LLM 提供商
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default LLMProviderStatusPanel;
