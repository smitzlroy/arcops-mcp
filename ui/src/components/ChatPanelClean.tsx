/**
 * ChatPanelClean - Simplified chat interface for ArcOps Assistant
 *
 * Features:
 * - Clean model selector with groups (recommended, tools, chat-only)
 * - Simple chat with tool execution display
 * - No complex streaming - just reliable sync requests
 */

import { useState, useRef, useEffect } from "react";

// Types
interface Message {
  role: "user" | "assistant";
  content: string;
  toolsExecuted?: ToolExecution[] | undefined;
  timestamp: Date;
}

interface ToolExecution {
  name: string;
  arguments: Record<string, unknown>;
  result_summary: string;
}

interface FoundryModel {
  id: string;
  name: string;
  size: string;
  supports_tools: boolean;
  downloaded: boolean;
  running: boolean;
  recommended: boolean;
}

interface ModelGroups {
  recommended: FoundryModel[];
  with_tools: FoundryModel[];
  chat_only: FoundryModel[];
}

// Server URL - using clean API on port 8082
const SERVER_URL = "http://127.0.0.1:8082";

export function ChatPanelClean() {
  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState<FoundryModel[]>([]);
  const [groups, setGroups] = useState<ModelGroups | null>(null);
  const [currentModel, setCurrentModel] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("phi-4-mini");
  const [showModelPanel, setShowModelPanel] = useState(false);
  const [modelAction, setModelAction] = useState<
    "starting" | "stopping" | null
  >(null);
  const [dryRun, setDryRun] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Load models on mount
  useEffect(() => {
    loadModels();
    checkStatus();

    // Add welcome message
    setMessages([
      {
        role: "assistant",
        content: `👋 **Welcome to ArcOps Assistant!**

I can help you diagnose Azure Local and AKS Arc issues using these tools:

- **Connectivity Check** - Test network access to 52+ Azure endpoints
- **Cluster Validation** - Check AKS Arc cluster health
- **TSG Search** - Find troubleshooting guides for errors
- **Known Issues** - Detect common AKS Arc problems
- **Log Collection** - Gather diagnostic logs

**Try asking:**
- "Check my connectivity to Azure"
- "Validate my cluster"
- "I have error 0x800xxxxx"

${dryRun ? "🧪 **Dry-run mode enabled** - using test data" : ""}`,
        timestamp: new Date(),
      },
    ]);
  }, []);

  // Load models from API
  const loadModels = async () => {
    try {
      const response = await fetch(`${SERVER_URL}/api/models`);
      const data = await response.json();
      setModels(data.models);
      setGroups(data.groups);
      setCurrentModel(data.current_model);

      // Auto-select a downloaded model with tools
      if (!currentModel) {
        const downloadedWithTools = data.models.find(
          (m: FoundryModel) => m.downloaded && m.supports_tools,
        );
        if (downloadedWithTools) {
          setSelectedModel(downloadedWithTools.id);
        }
      }
    } catch (e) {
      console.error("Failed to load models:", e);
    }
  };

  // Check current status
  const checkStatus = async () => {
    try {
      const response = await fetch(`${SERVER_URL}/api/status`);
      const data = await response.json();
      setCurrentModel(data.current_model);
    } catch (e) {
      console.error("Failed to check status:", e);
    }
  };

  // Start a model
  const startModel = async (modelId: string) => {
    setModelAction("starting");

    const model = models.find((m) => m.id === modelId);
    const needsDownload = model && !model.downloaded;

    // Add status message
    addMessage(
      "assistant",
      needsDownload
        ? `⬇️ Downloading **${model?.name}** (${model?.size})... This may take a few minutes.`
        : `▶️ Starting **${model?.name || modelId}**...`,
    );

    try {
      const response = await fetch(`${SERVER_URL}/api/models/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      const data = await response.json();

      if (data.success) {
        addMessage(
          "assistant",
          `✅ **${model?.name || modelId}** is now running! You can start chatting.`,
        );
        setCurrentModel(modelId);
        setShowModelPanel(false);
        await loadModels();
      } else {
        addMessage(
          "assistant",
          `❌ Failed to start model: ${data.error}\n\n${data.hint ? `💡 ${data.hint}` : ""}`,
        );
      }
    } catch (e) {
      addMessage("assistant", `❌ Failed to start model: ${e}`);
    } finally {
      setModelAction(null);
    }
  };

  // Stop current model
  const stopModel = async () => {
    setModelAction("stopping");
    try {
      await fetch(`${SERVER_URL}/api/models/stop`, { method: "POST" });
      setCurrentModel(null);
      addMessage("assistant", "⏹️ Model stopped.");
      await loadModels();
    } catch (e) {
      console.error("Failed to stop model:", e);
    } finally {
      setModelAction(null);
    }
  };

  // Add a message
  const addMessage = (
    role: "user" | "assistant",
    content: string,
    toolsExecuted?: ToolExecution[],
  ) => {
    const newMessage: Message = {
      role,
      content,
      toolsExecuted: toolsExecuted || undefined,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, newMessage]);
  };

  // Send a chat message
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    addMessage("user", userMessage);
    setIsLoading(true);

    try {
      const response = await fetch(`${SERVER_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          dry_run: dryRun,
        }),
      });

      const data = await response.json();

      if (data.success) {
        addMessage("assistant", data.response, data.tools_executed);
      } else {
        addMessage("assistant", `⚠️ ${data.error || "Something went wrong"}`);
      }
    } catch (e) {
      if (!currentModel) {
        addMessage(
          "assistant",
          "⚠️ No model is running. Click **Configure** to start one.",
        );
      } else {
        addMessage("assistant", `❌ Error: ${e}`);
      }
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  // Handle key press
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-screen relative">
      {/* Floating particles background */}
      <div className="particles">
        {[...Array(10)].map((_, i) => (
          <div
            key={i}
            className="particle"
            style={{ left: `${5 + i * 10}%`, animationDelay: `${i * 0.5}s` }}
          />
        ))}
      </div>

      {/* Header */}
      <header className="relative z-10 glass-card rounded-none border-x-0 border-t-0 header-border">
        <div className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-purple-700 flex items-center justify-center text-xl shadow-lg">
                ☁️
              </div>
              <div>
                <h1 className="text-xl font-bold gradient-text">
                  ArcOps Assistant
                </h1>
                <p className="text-sm text-gray-400">
                  Powered by Foundry Local
                </p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {/* Status indicator */}
              <div className="flex items-center gap-2 text-sm text-gray-300">
                <span
                  className={`status-dot ${currentModel ? "online" : "offline"}`}
                />
                <span>{currentModel || "No model"}</span>
              </div>
              {/* Dry-run toggle */}
              <label className="flex items-center gap-2 text-sm cursor-pointer text-gray-300 hover:text-white transition-colors">
                <input
                  type="checkbox"
                  checked={dryRun}
                  onChange={(e) => setDryRun(e.target.checked)}
                  className="rounded bg-gray-700 border-gray-600 text-purple-500 focus:ring-purple-500"
                />
                <span>Dry-run</span>
              </label>
              {/* Configure button */}
              <button
                onClick={() => setShowModelPanel(!showModelPanel)}
                className="px-4 py-2 glass-card glow-purple hover:scale-105 transition-all text-sm font-medium"
              >
                Configure
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Model Panel (collapsible) */}
      {showModelPanel && (
        <div className="relative z-10 glass-card rounded-none border-x-0 p-4">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-lg font-semibold mb-4 text-white">
              Model Selection
            </h2>

            {/* Current model info */}
            {currentModel && (
              <div className="mb-4 p-3 glass-card glow-green flex items-center justify-between">
                <div>
                  <span className="font-medium text-green-400">
                    Currently running:{" "}
                  </span>
                  <span className="text-green-300">{currentModel}</span>
                </div>
                <button
                  onClick={stopModel}
                  disabled={modelAction === "stopping"}
                  className="px-3 py-1 bg-red-500/20 border border-red-500/50 text-red-400 rounded hover:bg-red-500/30 disabled:opacity-50 transition-colors"
                >
                  {modelAction === "stopping" ? "Stopping..." : "Stop"}
                </button>
              </div>
            )}

            {/* Model groups */}
            {groups && (
              <div className="space-y-4">
                {/* Recommended */}
                {groups.recommended.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-yellow-400 mb-2">
                      ⭐ Recommended for Tools
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      {groups.recommended.map((model) => (
                        <ModelCard
                          key={model.id}
                          model={model}
                          isSelected={selectedModel === model.id}
                          onSelect={() => setSelectedModel(model.id)}
                          onStart={() => startModel(model.id)}
                          isStarting={
                            modelAction === "starting" &&
                            selectedModel === model.id
                          }
                          isCurrent={currentModel === model.id}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* With Tools */}
                {groups.with_tools.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-purple-400 mb-2">
                      🛠️ Tool-Capable Models
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      {groups.with_tools.map((model) => (
                        <ModelCard
                          key={model.id}
                          model={model}
                          isSelected={selectedModel === model.id}
                          onSelect={() => setSelectedModel(model.id)}
                          onStart={() => startModel(model.id)}
                          isStarting={
                            modelAction === "starting" &&
                            selectedModel === model.id
                          }
                          isCurrent={currentModel === model.id}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {/* Chat Only */}
                {groups.chat_only.length > 0 && (
                  <details className="mt-4">
                    <summary className="text-sm font-semibold text-gray-500 cursor-pointer mb-2 hover:text-gray-400 transition-colors">
                      💬 Chat-Only Models ({groups.chat_only.length}) - Cannot
                      use diagnostic tools
                    </summary>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-2">
                      {groups.chat_only.map((model) => (
                        <ModelCard
                          key={model.id}
                          model={model}
                          isSelected={selectedModel === model.id}
                          onSelect={() => setSelectedModel(model.id)}
                          onStart={() => startModel(model.id)}
                          isStarting={
                            modelAction === "starting" &&
                            selectedModel === model.id
                          }
                          isCurrent={currentModel === model.id}
                          disabled={true}
                        />
                      ))}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 relative z-10">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}
          {isLoading && (
            <div className="flex items-center gap-3 text-gray-400 glass-card p-4 w-fit">
              <div className="flex gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500 thinking-dot"></span>
                <span className="w-2 h-2 rounded-full bg-purple-500 thinking-dot"></span>
                <span className="w-2 h-2 rounded-full bg-purple-500 thinking-dot"></span>
              </div>
              <span>Thinking...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="relative z-10 glass-card rounded-none border-x-0 border-b-0 p-4">
        <div className="max-w-4xl mx-auto flex gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={
              currentModel
                ? "Ask about Azure Local or AKS Arc..."
                : "Start a model first..."
            }
            disabled={!currentModel && !dryRun}
            className="flex-1 p-3 bg-white/5 border border-white/10 rounded-xl resize-none text-white placeholder-gray-500 input-glow disabled:opacity-50 disabled:cursor-not-allowed"
            rows={2}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || (!currentModel && !dryRun) || !input.trim()}
            className="px-6 py-3 btn-primary rounded-xl font-medium"
          >
            Send
          </button>
        </div>
        <p className="text-center text-xs text-gray-500 mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

// Model Card Component
function ModelCard({
  model,
  isSelected,
  onSelect,
  onStart,
  isStarting,
  isCurrent,
  disabled = false,
}: {
  model: FoundryModel;
  isSelected: boolean;
  onSelect: () => void;
  onStart: () => void;
  isStarting: boolean;
  isCurrent: boolean;
  disabled?: boolean;
}) {
  return (
    <div
      className={`p-3 glass-card cursor-pointer transition-all ${
        isCurrent
          ? "glow-green border-green-500/50"
          : isSelected
            ? "glow-purple border-purple-500/50"
            : disabled
              ? "opacity-40"
              : "hover:border-purple-500/30"
      }`}
      onClick={disabled ? undefined : onSelect}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="font-medium text-sm text-white">{model.name}</span>
        <div className="flex items-center gap-1">
          {model.recommended && (
            <span className="text-yellow-400 text-xs">★</span>
          )}
          {model.supports_tools && (
            <span className="text-purple-400 text-xs" title="Supports tools">
              🛠️
            </span>
          )}
        </div>
      </div>
      <div className="text-xs text-gray-400 mb-2">
        {model.size} •{" "}
        {model.downloaded ? "✓ Downloaded" : "⬇️ Download needed"}
      </div>
      {!isCurrent && !disabled && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onStart();
          }}
          disabled={isStarting}
          className={`w-full py-1.5 px-2 text-xs rounded-lg transition-all ${
            model.downloaded
              ? "bg-green-500/20 border border-green-500/50 text-green-400 hover:bg-green-500/30"
              : "bg-purple-500/20 border border-purple-500/50 text-purple-400 hover:bg-purple-500/30"
          } disabled:opacity-50`}
        >
          {isStarting
            ? "Starting..."
            : model.downloaded
              ? "Start"
              : "Download & Start"}
        </button>
      )}
      {isCurrent && (
        <div className="text-xs text-green-400 font-medium text-center">
          ✓ Running
        </div>
      )}
    </div>
  );
}

// Message Bubble Component
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in-up`}
    >
      <div
        className={`max-w-[80%] rounded-2xl p-4 ${
          isUser
            ? "bg-gradient-to-br from-purple-600 to-purple-800 text-white"
            : "glass-card glow-cyan"
        }`}
      >
        {/* Content with markdown-like rendering */}
        <div
          className={`prose prose-sm max-w-none ${isUser ? "text-white prose-invert" : "text-gray-200"}`}
          dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
        />

        {/* Tool executions */}
        {message.toolsExecuted && message.toolsExecuted.length > 0 && (
          <div className="mt-3 pt-3 border-t border-white/10">
            <p className="text-xs font-semibold text-orange-400 mb-2">
              🛠️ Tools Used:
            </p>
            {message.toolsExecuted.map((tool, idx) => (
              <div key={idx} className="text-xs tool-card mb-1">
                <span className="font-medium text-orange-400">{tool.name}</span>
                <span className="text-gray-400 ml-2">
                  → {tool.result_summary}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs mt-2 ${isUser ? "text-purple-200" : "text-gray-500"}`}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

// Simple markdown formatter
function formatMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(
      /`(.+?)`/g,
      '<code class="bg-white/10 px-1.5 py-0.5 rounded text-cyan-300">$1</code>',
    )
    .replace(/\n/g, "<br/>");
}

export default ChatPanelClean;
