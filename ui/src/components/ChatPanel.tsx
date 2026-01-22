import { useState, useRef, useEffect } from "react";
import { LiveToolVisualization } from "./LiveToolVisualization";

interface ToolCall {
  tool: string;
  result: unknown;
}

interface ToolExecution {
  toolId: string;
  toolName: string;
  icon: string;
  status: "pending" | "running" | "success" | "error";
  startTime?: number;
  duration?: number;
}

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
  toolCalls?: ToolCall[];
  timestamp: Date;
}

interface FoundryModel {
  id: string;
  name: string;
  size: string;
  sizeBytes?: number;
  recommended: boolean;
  downloaded: boolean;
  loaded: boolean;
  supportsTools?: boolean;
  license?: string;
}

interface ChatStatus {
  available: boolean;
  models: string[];
  error?: string;
  hint?: string;
}

interface ChatPanelProps {
  serverUrl: string;
  onClose?: () => void;
}

interface ToolInfo {
  id: string;
  name: string;
  icon: string;
  description?: string;
}

interface StreamEvent {
  type:
    | "phase"
    | "scanning"
    | "selected"
    | "executing"
    | "tool_complete"
    | "complete"
    | "error";
  phase?: string;
  message?: string;
  tool?: ToolInfo;
  highlight?: boolean;
  args?: Record<string, unknown>;
  success?: boolean;
  content?: string;
  tool_calls?: ToolCall[];
  error?: string;
}

// Tool name to friendly name mapping
const TOOL_NAMES: Record<string, { name: string; icon: string }> = {
  run_connectivity_check: {
    name: "Azure Connectivity Check",
    icon: "🌐",
  },
  check_environment: {
    name: "Environment Validation",
    icon: "🔍",
  },
  validate_cluster: {
    name: "AKS Arc Cluster Validation",
    icon: "☸️",
  },
  search_tsg: {
    name: "TSG Search",
    icon: "📚",
  },
};

// Interface for check items in results
interface CheckResult {
  id: string;
  title: string;
  status: string;
  severity?: string;
  hint?: string;
  evidence?: Record<string, unknown>;
}

interface ResultSummary {
  total: number;
  pass: number;
  fail: number;
  warn: number;
  skipped?: number;
}

// Component to display tool call results nicely
function ToolCallDisplay({ toolCall }: { toolCall: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const toolInfo = TOOL_NAMES[toolCall.tool] || {
    name: toolCall.tool,
    icon: "🔧",
  };

  // Extract data from result
  const result = toolCall.result as Record<string, unknown> | null;
  const hasError = Boolean(result?.["error"]);
  const errorMessage = result?.["error"] ? String(result["error"]) : "";
  const checks = result?.["checks"] as CheckResult[] | undefined;
  const summary = result?.["summary"] as ResultSummary | undefined;

  // Count by status (lowercase)
  const passCount =
    summary?.pass ?? checks?.filter((c) => c.status === "pass").length ?? 0;
  const failCount =
    summary?.fail ?? checks?.filter((c) => c.status === "fail").length ?? 0;
  const warnCount =
    summary?.warn ?? checks?.filter((c) => c.status === "warn").length ?? 0;
  const totalCount = summary?.total ?? checks?.length ?? 0;
  const hasChecks = Boolean(checks && checks.length > 0);

  // Get issues that need attention
  const issues =
    checks?.filter((c) => c.status === "fail" || c.status === "warn") ?? [];

  // Determine overall status
  const overallStatus =
    failCount > 0 ? "error" : warnCount > 0 ? "warning" : "success";
  const statusColors = {
    success: "bg-green-50 border-green-200",
    warning: "bg-yellow-50 border-yellow-200",
    error: "bg-red-50 border-red-200",
  };
  const statusIcon = {
    success: "✅",
    warning: "⚠️",
    error: "❌",
  };

  return (
    <div
      className={`rounded-lg overflow-hidden border-2 ${statusColors[overallStatus]}`}
    >
      {/* Header with summary */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-white/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">{toolInfo.icon}</span>
          <div className="text-left">
            <span className="font-semibold text-gray-800 block">
              {toolInfo.name}
            </span>
            {hasChecks && (
              <span className="text-sm text-gray-600">
                {statusIcon[overallStatus]} {passCount} passed
                {warnCount > 0 && `, ${warnCount} warnings`}
                {failCount > 0 && `, ${failCount} failed`} of {totalCount}{" "}
                checks
              </span>
            )}
          </div>
        </div>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${expanded ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Summary bar */}
      {hasChecks && !expanded ? (
        <div className="px-4 pb-3">
          <div className="flex h-2 rounded-full overflow-hidden bg-gray-200">
            {passCount > 0 && (
              <div
                className="bg-green-500"
                style={{ width: `${(passCount / totalCount) * 100}%` }}
              />
            )}
            {warnCount > 0 && (
              <div
                className="bg-yellow-500"
                style={{ width: `${(warnCount / totalCount) * 100}%` }}
              />
            )}
            {failCount > 0 && (
              <div
                className="bg-red-500"
                style={{ width: `${(failCount / totalCount) * 100}%` }}
              />
            )}
          </div>
        </div>
      ) : null}

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-gray-200 bg-white">
          {/* Issues first */}
          {issues.length > 0 && (
            <div className="p-4 border-b border-gray-100">
              <h4 className="font-medium text-gray-700 mb-2 flex items-center gap-2">
                <span>⚡</span> Items Needing Attention ({issues.length})
              </h4>
              <div className="space-y-2">
                {issues.map((check, i) => (
                  <div
                    key={i}
                    className={`p-3 rounded-lg ${check.status === "fail" ? "bg-red-50" : "bg-yellow-50"}`}
                  >
                    <div className="flex items-start gap-2">
                      <span className="text-lg">
                        {check.status === "fail" ? "❌" : "⚠️"}
                      </span>
                      <div className="flex-1">
                        <p className="font-medium text-gray-800">
                          {check.title}
                        </p>
                        {check.hint && (
                          <p className="text-sm text-gray-600 mt-1">
                            💡 {check.hint}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* All checks */}
          <div className="p-4">
            <h4 className="font-medium text-gray-700 mb-2">All Checks</h4>
            <div className="space-y-1">
              {checks?.map((check, i) => (
                <div key={i} className="flex items-center gap-2 py-1 text-sm">
                  <span>
                    {check.status === "pass"
                      ? "✅"
                      : check.status === "warn"
                        ? "⚠️"
                        : "❌"}
                  </span>
                  <span
                    className={
                      check.status === "pass"
                        ? "text-gray-600"
                        : "text-gray-800"
                    }
                  >
                    {check.title}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Error display */}
      {hasError ? (
        <div className="p-4 bg-red-50 border-t border-red-200">
          <p className="text-red-700 text-sm">{errorMessage}</p>
        </div>
      ) : null}
    </div>
  );
}

// Simple markdown-like renderer
function FormattedContent({ content }: { content: string }) {
  // Process content line by line
  const lines = content.split("\n");

  return (
    <div className="space-y-2 text-sm">
      {lines.map((line, i) => {
        // Skip empty lines but preserve spacing
        if (!line.trim()) {
          return <div key={i} className="h-2" />;
        }

        // Headers with **
        if (line.startsWith("**") && line.includes(":**")) {
          const headerText = line.replace(/\*\*/g, "");
          return (
            <p key={i} className="font-semibold text-gray-800 mt-3 first:mt-0">
              {headerText}
            </p>
          );
        }

        // Bullet points with - or •
        if (line.trim().startsWith("- ") || line.trim().startsWith("• ")) {
          const bulletText = line.trim().slice(2);
          // Process inline bold
          const parts = bulletText.split(/(\*\*[^*]+\*\*)/g);
          return (
            <div key={i} className="flex items-start gap-2 ml-2">
              <span className="text-gray-400">•</span>
              <span className="text-gray-700">
                {parts.map((part, j) =>
                  part.startsWith("**") && part.endsWith("**") ? (
                    <strong key={j}>{part.slice(2, -2)}</strong>
                  ) : (
                    part
                  ),
                )}
              </span>
            </div>
          );
        }

        // Hint lines with 💡
        if (line.trim().startsWith("💡")) {
          return (
            <div key={i} className="ml-4 text-gray-600 italic text-xs">
              {line.trim()}
            </div>
          );
        }

        // Process inline bold and return paragraph
        const parts = line.split(/(\*\*[^*]+\*\*)/g);
        return (
          <p key={i} className="text-gray-700">
            {parts.map((part, j) =>
              part.startsWith("**") && part.endsWith("**") ? (
                <strong key={j} className="font-semibold">
                  {part.slice(2, -2)}
                </strong>
              ) : (
                part
              ),
            )}
          </p>
        );
      })}
    </div>
  );
}

export function ChatPanel({ serverUrl, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        'Hello! I\'m ArcOps Assistant. I can help you diagnose Azure Local and AKS Arc issues. Try asking me:\n\n• "Check connectivity to Azure"\n• "Validate my cluster"\n• "I have error 0x800xxxxx" (searches troubleshooting guides)\n\nWhat would you like to do?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatStatus, setChatStatus] = useState<ChatStatus | null>(null);
  const [availableModels, setAvailableModels] = useState<FoundryModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [selectedModel, setSelectedModel] = useState("qwen2.5-1.5b");
  const [modelAction, setModelAction] = useState<
    "starting" | "stopping" | null
  >(null);
  const [showModelConfig, setShowModelConfig] = useState(true); // Always show initially
  const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([]);
  const [executionComplete, setExecutionComplete] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check chat status and load models
  useEffect(() => {
    checkChatStatus();
    loadAvailableModels();
  }, [serverUrl]);

  const checkChatStatus = async () => {
    try {
      const response = await fetch(`${serverUrl}/api/chat/status`);
      const data = await response.json();
      setChatStatus(data);
    } catch {
      setChatStatus({
        available: false,
        models: [],
        error: "Server not reachable",
      });
    }
  };

  const loadAvailableModels = async () => {
    setModelsLoading(true);
    try {
      const response = await fetch(`${serverUrl}/api/foundry/models`);
      const data = await response.json();
      console.log("Foundry models response:", data);
      if (data.success && data.models) {
        setAvailableModels(data.models);
        // Select first loaded model or recommended
        const loadedModel = data.models.find((m: FoundryModel) => m.loaded);
        const recommended = data.models.find(
          (m: FoundryModel) => m.recommended,
        );
        setSelectedModel(loadedModel?.id || recommended?.id || "qwen2.5-1.5b");
      }
    } catch (err) {
      console.error("Failed to load models:", err);
    } finally {
      setModelsLoading(false);
    }
  };

  const startModel = async () => {
    setModelAction("starting");
    try {
      const response = await fetch(`${serverUrl}/api/foundry/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: selectedModel }),
      });
      const data = await response.json();
      if (data.success) {
        // Refresh status
        await checkChatStatus();
        await loadAvailableModels();
        setShowModelConfig(false);
      } else {
        // Show error in chat
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `⚠️ Failed to start model: ${data.error}\n\n${data.hint ? `💡 ${data.hint}` : ""}`,
            timestamp: new Date(),
          },
        ]);
      }
    } catch (e) {
      console.error("Failed to start model:", e);
    } finally {
      setModelAction(null);
    }
  };

  const stopModel = async () => {
    setModelAction("stopping");
    try {
      await fetch(`${serverUrl}/api/foundry/stop`, { method: "POST" });
      await checkChatStatus();
      await loadAvailableModels();
    } catch (e) {
      console.error("Failed to stop model:", e);
    } finally {
      setModelAction(null);
    }
  };

  const switchModel = async (newModelId: string) => {
    // Don't switch if already selected and loaded
    if (newModelId === selectedModel) {
      const model = availableModels.find((m) => m.id === newModelId);
      if (model?.loaded) return;
    }

    setSelectedModel(newModelId);
    const model = availableModels.find((m) => m.id === newModelId);

    // If model is already loaded, just select it
    if (model?.loaded) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `✅ Switched to ${model.name}. Ready to help!`,
          timestamp: new Date(),
        },
      ]);
      return;
    }

    // Need to start/restart with this model
    setModelAction("starting");
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: `🔄 ${model?.downloaded ? "Starting" : "Downloading and starting"} ${model?.name || newModelId}... This may take a moment.`,
        timestamp: new Date(),
      },
    ]);

    try {
      // Use restart if a model is running, otherwise start
      const endpoint = chatStatus?.available
        ? `${serverUrl}/api/foundry/restart`
        : `${serverUrl}/api/foundry/start`;

      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: newModelId }),
      });
      const data = await response.json();

      if (data.success) {
        await checkChatStatus();
        await loadAvailableModels();
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `✅ ${model?.name || newModelId} is ready! How can I help you?`,
            timestamp: new Date(),
          },
        ]);
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `⚠️ Failed to start model: ${data.error || "Unknown error"}\n\n${data.hint ? `💡 ${data.hint}` : ""}`,
            timestamp: new Date(),
          },
        ]);
      }
    } catch (e) {
      console.error("Failed to switch model:", e);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Failed to switch model. Please try again or check if Foundry Local is running.`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setModelAction(null);
    }
  };

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setExecutionComplete(false);
    setToolExecutions([]);

    // Build messages array for API
    const apiMessages = messages
      .filter((m) => m.role !== "system")
      .map((m) => ({ role: m.role, content: m.content }));
    apiMessages.push({ role: "user", content: userMessage.content });

    try {
      // Use streaming endpoint for real-time progress
      const response = await fetch(`${serverUrl}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error("No response body");
      }

      let scannedTools: ToolExecution[] = [];
      let selectedTool: ToolExecution | null = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;

          try {
            const event: StreamEvent = JSON.parse(line.slice(6));

            switch (event.type) {
              case "phase":
                // Update phase indicator
                if (event.phase === "analyzing") {
                  setToolExecutions([
                    {
                      toolId: "analyzing",
                      toolName: event.message || "Analyzing...",
                      icon: "🧠",
                      status: "running",
                      startTime: Date.now(),
                    },
                  ]);
                } else if (event.phase === "thinking") {
                  setToolExecutions((prev) =>
                    prev.map((t) =>
                      t.toolId === "analyzing"
                        ? { ...t, toolName: event.message || "Thinking..." }
                        : t,
                    ),
                  );
                }
                break;

              case "scanning":
                // Show tool being scanned with animation
                if (event.tool) {
                  const isHighlighted = event.highlight === true;
                  const scanExec: ToolExecution = {
                    toolId: event.tool.id,
                    toolName: event.tool.name,
                    icon: event.tool.icon,
                    status: isHighlighted ? "running" : "pending",
                    startTime: Date.now(),
                  };
                  scannedTools = [...scannedTools, scanExec];
                  // Show scanning visualization - highlight the selected one
                  setToolExecutions([
                    {
                      toolId: "mcp_scanning",
                      toolName: isHighlighted
                        ? `Found: ${event.tool.name}`
                        : "Scanning MCP tools...",
                      icon: "🔌",
                      status: "running",
                      startTime: Date.now(),
                    },
                    ...scannedTools.map((t) => ({
                      ...t,
                      status: (t.toolId === event.tool?.id && isHighlighted
                        ? "success"
                        : t.toolId === event.tool?.id
                          ? "running"
                          : "pending") as "running" | "pending" | "success",
                    })),
                  ]);
                }
                break;

              case "selected":
                // Tool selected - highlight it
                if (event.tool) {
                  selectedTool = {
                    toolId: event.tool.id,
                    toolName: event.tool.name,
                    icon: event.tool.icon,
                    status: "running",
                    startTime: Date.now(),
                  };
                  setToolExecutions([selectedTool]);
                }
                break;

              case "executing":
                // Tool is executing
                if (selectedTool) {
                  setToolExecutions([{ ...selectedTool, status: "running" }]);
                }
                break;

              case "tool_complete":
                // Tool finished
                if (selectedTool && event.tool) {
                  setToolExecutions([
                    {
                      ...selectedTool,
                      status: event.success ? "success" : "error",
                    },
                  ]);
                }
                break;

              case "complete":
                // Request complete
                setExecutionComplete(true);
                if (event.tool_calls && event.tool_calls.length > 0) {
                  const executions: ToolExecution[] = event.tool_calls.map(
                    (tc: ToolCall) => {
                      const toolInfo = TOOL_NAMES[tc.tool] || {
                        name: tc.tool,
                        icon: "🔧",
                      };
                      return {
                        toolId: tc.tool,
                        toolName: toolInfo.name,
                        icon: toolInfo.icon,
                        status: "success" as const,
                        startTime: Date.now(),
                      };
                    },
                  );
                  setToolExecutions(executions);
                }
                const newMessage: Message = {
                  role: "assistant",
                  content: event.content || "I've processed your request.",
                  timestamp: new Date(),
                };
                if (event.tool_calls && event.tool_calls.length > 0) {
                  newMessage.toolCalls = event.tool_calls;
                }
                setMessages((prev) => [...prev, newMessage]);
                break;

              case "error":
                setMessages((prev) => [
                  ...prev,
                  {
                    role: "assistant",
                    content: `⚠️ ${event.error || "Something went wrong."}`,
                    timestamp: new Date(),
                  },
                ]);
                break;
            }
          } catch {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    } catch (error) {
      // Fallback to non-streaming endpoint if streaming fails
      try {
        const response = await fetch(`${serverUrl}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: apiMessages }),
        });
        const data = await response.json();

        if (data.success) {
          if (data.tool_calls && data.tool_calls.length > 0) {
            const executions: ToolExecution[] = data.tool_calls.map(
              (tc: ToolCall) => {
                const toolInfo = TOOL_NAMES[tc.tool] || {
                  name: tc.tool,
                  icon: "🔧",
                };
                return {
                  toolId: tc.tool,
                  toolName: toolInfo.name,
                  icon: toolInfo.icon,
                  status: "success" as const,
                  startTime: Date.now(),
                };
              },
            );
            setToolExecutions(executions);
            setExecutionComplete(true);
          }
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: data.content || "I've processed your request.",
              toolCalls: data.tool_calls,
              timestamp: new Date(),
            },
          ]);
        } else {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: `⚠️ ${data.error || "Something went wrong."}${data.hint ? `\n\n💡 ${data.hint}` : ""}`,
              timestamp: new Date(),
            },
          ]);
        }
      } catch (fallbackError) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `⚠️ Failed to connect to chat service. Is the MCP server running?\n\nError: ${error instanceof Error ? error.message : "Unknown error"}`,
            timestamp: new Date(),
          },
        ]);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-700 text-white">
        <div className="flex items-center gap-2">
          <span className="text-xl">💬</span>
          <div>
            <h3 className="font-semibold">ArcOps Assistant</h3>
            <p className="text-xs text-blue-100">
              {chatStatus?.available && chatStatus.models.length > 0
                ? `Using ${chatStatus.models[0]}`
                : "Powered by Foundry Local"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Model config button */}
          <button
            onClick={() => setShowModelConfig(!showModelConfig)}
            className="p-1.5 hover:bg-white/20 rounded transition-colors"
            title="AI Model Settings"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
          </button>
          {/* Status indicator */}
          <div
            className={`w-2 h-2 rounded-full ${
              chatStatus === null
                ? "bg-gray-400"
                : chatStatus.available
                  ? "bg-green-400"
                  : "bg-red-400"
            }`}
            title={
              chatStatus === null
                ? "Checking..."
                : chatStatus.available
                  ? "AI Ready"
                  : "AI Not Available"
            }
          />
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 hover:bg-white/20 rounded transition-colors"
              aria-label="Close chat"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Model Configuration Panel - Compact Dropdown Design */}
      {showModelConfig && (
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            {/* Model Dropdown */}
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-500 mb-1">
                AI Model
              </label>
              <div className="relative">
                <select
                  value={selectedModel}
                  onChange={(e) => switchModel(e.target.value)}
                  disabled={modelAction !== null || modelsLoading}
                  className="w-full appearance-none bg-white border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm font-medium text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
                >
                  {modelsLoading ? (
                    <option>Loading models...</option>
                  ) : (
                    <>
                      {/* Downloaded models with tools */}
                      {availableModels.filter(
                        (m) => m.supportsTools && m.downloaded,
                      ).length > 0 && (
                        <optgroup label="✓ Recommended (Tool Support)">
                          {availableModels
                            .filter((m) => m.supportsTools && m.downloaded)
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.loaded ? "▶ " : ""}
                                {model.name} ({model.size})
                                {model.recommended ? " ★" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}

                      {/* Downloaded models without tools */}
                      {availableModels.filter(
                        (m) => !m.supportsTools && m.downloaded,
                      ).length > 0 && (
                        <optgroup label="💬 Chat Only (Downloaded)">
                          {availableModels
                            .filter((m) => !m.supportsTools && m.downloaded)
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.loaded ? "▶ " : ""}
                                {model.name} ({model.size})
                              </option>
                            ))}
                        </optgroup>
                      )}

                      {/* Not downloaded */}
                      {availableModels.filter((m) => !m.downloaded).length >
                        0 && (
                        <optgroup label="⬇ Available to Download">
                          {availableModels
                            .filter((m) => !m.downloaded)
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                ⬇ {model.name} ({model.size})
                                {model.supportsTools ? " ✓Tools" : ""}
                                {model.recommended ? " ★" : ""}
                              </option>
                            ))}
                        </optgroup>
                      )}
                    </>
                  )}
                </select>
                <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                  <svg
                    className="w-4 h-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>
              </div>
            </div>

            {/* Action Button */}
            <div className="flex-shrink-0">
              <label className="block text-xs font-medium text-gray-500 mb-1">
                &nbsp;
              </label>
              {!chatStatus?.available ? (
                <button
                  onClick={startModel}
                  disabled={modelAction !== null}
                  className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2 min-w-[100px] justify-center"
                >
                  {modelAction === "starting" ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      <span className="hidden sm:inline">
                        {availableModels.find((m) => m.id === selectedModel)
                          ?.downloaded
                          ? "Starting"
                          : "Downloading"}
                      </span>
                    </>
                  ) : (
                    <>
                      <span>
                        {availableModels.find((m) => m.id === selectedModel)
                          ?.downloaded
                          ? "▶"
                          : "⬇"}
                      </span>
                      <span>
                        {availableModels.find((m) => m.id === selectedModel)
                          ?.downloaded
                          ? "Start"
                          : "Download"}
                      </span>
                    </>
                  )}
                </button>
              ) : (
                <button
                  onClick={stopModel}
                  disabled={modelAction !== null}
                  className="px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2 min-w-[100px] justify-center"
                >
                  {modelAction === "stopping" ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      <span className="hidden sm:inline">Stopping</span>
                    </>
                  ) : modelAction === "starting" ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      <span className="hidden sm:inline">Switching</span>
                    </>
                  ) : (
                    <>
                      <span>⏹</span>
                      <span>Stop</span>
                    </>
                  )}
                </button>
              )}
            </div>

            {/* Close button */}
            <button
              onClick={() => setShowModelConfig(false)}
              className="flex-shrink-0 p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-200 rounded-lg transition-colors"
              title="Close settings"
            >
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Status bar */}
          <div className="mt-2 flex items-center gap-3 text-xs">
            {chatStatus?.available ? (
              <span className="flex items-center gap-1.5 text-green-700 bg-green-50 px-2 py-1 rounded-full">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                Running: {chatStatus.models.join(", ")}
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-gray-500">
                <span className="w-2 h-2 bg-gray-400 rounded-full"></span>
                Not running
              </span>
            )}

            {/* Model capability indicator */}
            {(() => {
              const model = availableModels.find((m) => m.id === selectedModel);
              if (!model) return null;

              if (!model.downloaded) {
                return (
                  <span className="text-blue-600 bg-blue-50 px-2 py-1 rounded-full">
                    ⬇ Will download {model.size}
                  </span>
                );
              }

              if (!model.supportsTools) {
                return (
                  <span className="text-amber-600 bg-amber-50 px-2 py-1 rounded-full">
                    ⚠ Chat only - no tool support
                  </span>
                );
              }

              return (
                <span className="text-green-600 bg-green-50 px-2 py-1 rounded-full">
                  ✓ Supports diagnostic tools
                </span>
              );
            })()}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, i) => (
          <div
            key={i}
            className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg ${
                message.role === "user"
                  ? "bg-blue-600 text-white px-4 py-2"
                  : "bg-gray-100 text-gray-800 px-4 py-2"
              }`}
            >
              {/* Tool calls display - show BEFORE content for assistant */}
              {message.role === "assistant" &&
                message.toolCalls &&
                message.toolCalls.length > 0 && (
                  <div className="mb-3 space-y-2">
                    <div className="flex items-center gap-2 text-xs text-gray-500 mb-2">
                      <span>🔧</span>
                      <span className="font-medium">
                        Ran {message.toolCalls.length} diagnostic
                        {message.toolCalls.length > 1 ? "s" : ""}
                      </span>
                    </div>
                    {message.toolCalls.map((tc, j) => (
                      <ToolCallDisplay key={j} toolCall={tc} />
                    ))}
                  </div>
                )}

              {/* Display formatted content */}
              {message.content &&
                (() => {
                  // Clean any remaining tool_call tags from content
                  const cleanContent = message.content
                    .replace(/<tool_call>[\s\S]*?<\/tool_call>/g, "")
                    .trim();

                  if (!cleanContent) return null;

                  // Use formatted content for assistant messages
                  if (message.role === "assistant") {
                    return <FormattedContent content={cleanContent} />;
                  }

                  // Plain text for user messages
                  return (
                    <p className="whitespace-pre-wrap text-sm">
                      {cleanContent}
                    </p>
                  );
                })()}

              <p className="text-xs opacity-60 mt-1">
                {message.timestamp.toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}

        {/* Loading indicator with live tool visualization */}
        {isLoading && (
          <div className="flex justify-start">
            <div className="max-w-[90%]">
              {toolExecutions.length > 0 ? (
                <LiveToolVisualization
                  executions={toolExecutions}
                  isComplete={executionComplete}
                />
              ) : (
                <div className="bg-gray-100 rounded-lg px-4 py-2">
                  <div className="flex items-center gap-2 text-gray-500">
                    <div className="animate-pulse flex gap-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
                    </div>
                    <span className="text-sm">Thinking...</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat unavailable warning */}
      {chatStatus !== null && !chatStatus.available && (
        <div className="px-4 py-2 bg-yellow-50 border-t border-yellow-200 flex items-center justify-between">
          <p className="text-xs text-yellow-800">
            <strong>⚠️ AI not available.</strong>{" "}
            {chatStatus.hint || "Start a model to enable chat."}
          </p>
          <button
            onClick={() => setShowModelConfig(true)}
            className="text-xs bg-yellow-200 hover:bg-yellow-300 px-2 py-1 rounded"
          >
            Configure
          </button>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-gray-200 p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask about Azure Local or AKS Arc..."
            className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={1}
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            title="Send message"
            aria-label="Send message"
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
              />
            </svg>
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Press Enter to send • Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

export default ChatPanel;
