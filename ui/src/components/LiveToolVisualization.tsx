import { useEffect, useState } from "react";

interface ToolExecution {
  toolId: string;
  toolName: string;
  icon: string;
  status: "pending" | "running" | "success" | "error";
  startTime?: number;
  duration?: number;
}

interface LiveToolVisualizationProps {
  executions: ToolExecution[];
  isComplete: boolean;
}

// Tool metadata
const TOOL_META: Record<string, { name: string; icon: string; color: string }> =
  {
    analyzing: {
      name: "Analyzing Request",
      icon: "🧠",
      color: "#a855f7",
    },
    mcp_scanning: {
      name: "Scanning MCP Tools",
      icon: "🔌",
      color: "#06b6d4",
    },
    run_connectivity_check: {
      name: "Azure Connectivity Check",
      icon: "🌐",
      color: "#50e6ff",
    },
    check_environment: {
      name: "Environment Validation",
      icon: "🔍",
      color: "#8661c5",
    },
    validate_cluster: {
      name: "AKS Arc Cluster Validation",
      icon: "☸️",
      color: "#0078d4",
    },
    search_tsg: {
      name: "TSG Search",
      icon: "📚",
      color: "#ffc107",
    },
  };

export function LiveToolVisualization({
  executions,
  isComplete,
}: LiveToolVisualizationProps) {
  const [animationStep, setAnimationStep] = useState(0);

  useEffect(() => {
    if (executions.length > 0 && !isComplete) {
      const interval = setInterval(() => {
        setAnimationStep((prev) => (prev + 1) % 4);
      }, 200);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [executions.length, isComplete]);

  if (executions.length === 0) return null;

  return (
    <div className="bg-gradient-to-r from-slate-900 to-slate-800 rounded-lg p-4 mb-3 border border-slate-700">
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="relative">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            🔌
          </div>
          {!isComplete && (
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-cyan-400 rounded-full animate-ping" />
          )}
        </div>
        <div>
          <h4 className="text-sm font-medium text-white">MCP Server</h4>
          <p className="text-xs text-slate-400">
            {isComplete
              ? `Completed ${executions.length} tool${executions.length > 1 ? "s" : ""}`
              : "Executing tools..."}
          </p>
        </div>
      </div>

      {/* Flow visualization */}
      <div className="relative">
        {/* Connection line */}
        <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-slate-600" />

        {/* Tool executions */}
        <div className="space-y-3 ml-10">
          {executions.map((exec, index) => {
            const meta = TOOL_META[exec.toolId] || {
              name: exec.toolName,
              icon: "🔧",
              color: "#0078d4",
            };
            const isRunning = exec.status === "running";
            const isPending = exec.status === "pending";
            const isSuccess = exec.status === "success";
            const isError = exec.status === "error";

            return (
              <div key={index} className="relative">
                {/* Animated connector */}
                <div className="absolute -left-10 top-1/2 -translate-y-1/2 flex items-center">
                  {/* Node on the line */}
                  <div
                    className={`w-3 h-3 rounded-full border-2 transition-all duration-300 ${
                      isRunning
                        ? "animate-pulse"
                        : isSuccess
                          ? "bg-green-500"
                          : isError
                            ? "bg-red-500"
                            : "bg-slate-600"
                    }`}
                    style={{
                      borderColor: isRunning ? meta.color : "transparent",
                      boxShadow: isRunning ? `0 0 10px ${meta.color}` : "none",
                    }}
                  />
                  {/* Animated dash to tool */}
                  <div
                    className="w-6 h-0.5 ml-1"
                    style={{
                      background: isRunning
                        ? `linear-gradient(90deg, ${meta.color}, transparent)`
                        : isPending
                          ? "#475569"
                          : isSuccess
                            ? "#22c55e"
                            : "#ef4444",
                    }}
                  >
                    {isRunning && (
                      <div
                        className="h-full bg-white opacity-50"
                        style={{
                          width: "4px",
                          marginLeft: `${animationStep * 6}px`,
                          transition: "margin-left 0.2s",
                        }}
                      />
                    )}
                  </div>
                </div>

                {/* Tool card */}
                <div
                  className={`p-3 rounded-lg border transition-all duration-300 ${
                    isRunning
                      ? "border-cyan-400 bg-slate-800"
                      : isPending
                        ? "border-slate-600 bg-slate-800/50 opacity-50"
                        : "border-slate-600 bg-slate-800"
                  }`}
                  style={{
                    boxShadow: isRunning ? `0 0 15px ${meta.color}40` : "none",
                  }}
                >
                  <div className="flex items-center gap-3">
                    {/* Tool icon */}
                    <div
                      className={`w-10 h-10 rounded-lg flex items-center justify-center text-xl ${
                        isRunning ? "animate-bounce" : ""
                      }`}
                      style={{
                        background: isRunning ? `${meta.color}30` : "#1e293b",
                      }}
                    >
                      {meta.icon}
                    </div>

                    {/* Tool info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h5 className="text-sm font-medium text-white truncate">
                          {meta.name}
                        </h5>
                        {isRunning && (
                          <div className="flex gap-1">
                            {[0, 1, 2].map((i) => (
                              <div
                                key={i}
                                className="w-1.5 h-1.5 rounded-full bg-cyan-400"
                                style={{
                                  opacity: animationStep % 3 === i ? 1 : 0.3,
                                }}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                      <p className="text-xs text-slate-400">
                        {isRunning
                          ? "Executing..."
                          : isPending
                            ? "Waiting..."
                            : isSuccess
                              ? `Completed${exec.duration ? ` in ${exec.duration}ms` : ""}`
                              : "Failed"}
                      </p>
                    </div>

                    {/* Status indicator */}
                    <div>
                      {isSuccess && (
                        <div className="w-6 h-6 rounded-full bg-green-500/20 flex items-center justify-center">
                          <svg
                            className="w-4 h-4 text-green-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M5 13l4 4L19 7"
                            />
                          </svg>
                        </div>
                      )}
                      {isError && (
                        <div className="w-6 h-6 rounded-full bg-red-500/20 flex items-center justify-center">
                          <svg
                            className="w-4 h-4 text-red-400"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                        </div>
                      )}
                      {isRunning && (
                        <div className="w-6 h-6">
                          <svg
                            className="animate-spin text-cyan-400"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                              fill="none"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                            />
                          </svg>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Result indicator */}
      {isComplete && (
        <div className="mt-3 pt-3 border-t border-slate-700 flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-green-500/20 flex items-center justify-center">
            <svg
              className="w-3 h-3 text-green-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <span className="text-xs text-slate-400">
            Tools executed successfully. See results below.
          </span>
        </div>
      )}
    </div>
  );
}

export default LiveToolVisualization;
