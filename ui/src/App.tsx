import { useState, useCallback, type DragEvent, type ChangeEvent } from "react";
import {
  type Findings,
  type Check,
  validateFindings,
  calculateSummary,
} from "./lib/schema";
import CheckCard from "./components/CheckCard";

interface AzureContext {
  subscription: string;
  subscriptionId: string;
  resourceGroup: string;
  clusterName: string;
  connected: boolean;
}

function App() {
  const [findings, setFindings] = useState<Findings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedChecks, setExpandedChecks] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<Check["status"] | "all">("all");
  const [mode, setMode] = useState<"dashboard" | "viewer">("dashboard");
  const [running, setRunning] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [azureContext, setAzureContext] = useState<AzureContext>({
    subscription: "",
    subscriptionId: "",
    resourceGroup: "",
    clusterName: "",
    connected: false,
  });

  const loadFindings = useCallback((data: unknown) => {
    if (validateFindings(data)) {
      // Calculate summary if not provided
      if (!data.summary) {
        data.summary = calculateSummary(data.checks);
      }
      setFindings(data);
      setError(null);
    } else {
      setError(
        "Invalid findings format. Please ensure the file matches the schema.",
      );
    }
  }, []);

  const handleFile = useCallback(
    (file: File) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const data = JSON.parse(e.target?.result as string);
          loadFindings(data);
        } catch {
          setError("Failed to parse JSON file.");
        }
      };
      reader.onerror = () => setError("Failed to read file.");
      reader.readAsText(file);
    },
    [loadFindings],
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOver(false);
  }, []);

  const handleFileInput = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const toggleCheck = useCallback((id: string) => {
    setExpandedChecks((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const exportBundle = useCallback(() => {
    if (!findings) return;

    const blob = new Blob([JSON.stringify(findings, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `findings-${findings.runId ?? "export"}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [findings]);

  const filteredChecks =
    findings?.checks.filter((c) => filter === "all" || c.status === filter) ??
    [];

  const runDiagnostic = useCallback(
    async (type: "envcheck" | "egress" | "validate") => {
      setRunning(type);
      setError(null);

      await new Promise((resolve) => setTimeout(resolve, 2000));

      const demoResult: Findings = {
        version: "1.0.0",
        target: type === "validate" ? "cluster" : "host",
        timestamp: new Date().toISOString(),
        runId: `${type}-${Date.now()}`,
        checks: [
          {
            id: `${type}-1`,
            title:
              type === "envcheck"
                ? "OS Version"
                : type === "egress"
                  ? "Azure ARM"
                  : "API Server",
            status: "pass",
            severity: "high",
            description: "Check passed",
          },
          {
            id: `${type}-2`,
            title:
              type === "envcheck"
                ? "Memory"
                : type === "egress"
                  ? "Azure AD"
                  : "Node Health",
            status: "pass",
            severity: "high",
            description: "Requirements met",
          },
          {
            id: `${type}-3`,
            title:
              type === "envcheck"
                ? "Disk Space"
                : type === "egress"
                  ? "ACR"
                  : "Pod Network",
            status: "pass",
            severity: "medium",
            description: "Sufficient",
          },
          {
            id: `${type}-4`,
            title:
              type === "envcheck"
                ? "Network"
                : type === "egress"
                  ? "Monitor"
                  : "DNS",
            status: "warn",
            severity: "medium",
            description: "Minor issue",
          },
          {
            id: `${type}-5`,
            title:
              type === "envcheck"
                ? "Hyper-V"
                : type === "egress"
                  ? "Key Vault"
                  : "Storage",
            status: "pass",
            severity: "low",
            description: "Configured",
          },
        ],
        summary: { total: 5, pass: 4, fail: 0, warn: 1, skipped: 0 },
      };

      setFindings(demoResult);
      setRunning(null);
    },
    [],
  );

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-gray-900 text-white py-4 px-6 shadow-lg">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">ArcOps MCP</h1>
            <p className="text-gray-400 text-sm">
              Azure Local & AKS Arc Diagnostics
            </p>
          </div>
          <div className="flex items-center gap-4">
            {/* Connection indicator */}
            <button
              onClick={() => setShowConfig(true)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm border ${
                azureContext.connected
                  ? "bg-green-900/30 text-green-400 border-green-600"
                  : "bg-yellow-900/30 text-yellow-400 border-yellow-600"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${azureContext.connected ? "bg-green-400" : "bg-yellow-400"}`}
              />
              {azureContext.connected
                ? azureContext.subscription
                : "Not Connected"}
            </button>

            {/* Nav buttons */}
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setMode("dashboard");
                  setFindings(null);
                }}
                className={`px-4 py-2 rounded text-sm font-medium ${mode === "dashboard" ? "bg-blue-600" : "bg-gray-700 hover:bg-gray-600"}`}
              >
                Dashboard
              </button>
              <button
                onClick={() => setMode("viewer")}
                className={`px-4 py-2 rounded text-sm font-medium ${mode === "viewer" ? "bg-blue-600" : "bg-gray-700 hover:bg-gray-600"}`}
              >
                Load Report
              </button>
              {findings && (
                <button
                  onClick={exportBundle}
                  className="px-4 py-2 bg-green-600 hover:bg-green-700 rounded text-sm font-medium"
                >
                  Export
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Config Modal */}
      {showConfig && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowConfig(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold mb-4">Azure Connection</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Subscription Name
                </label>
                <input
                  type="text"
                  placeholder="My Azure Subscription"
                  className="w-full px-3 py-2 border rounded-md"
                  value={azureContext.subscription}
                  onChange={(e) =>
                    setAzureContext((p) => ({
                      ...p,
                      subscription: e.target.value,
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Subscription ID
                </label>
                <input
                  type="text"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full px-3 py-2 border rounded-md font-mono text-sm"
                  value={azureContext.subscriptionId}
                  onChange={(e) =>
                    setAzureContext((p) => ({
                      ...p,
                      subscriptionId: e.target.value,
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Resource Group
                </label>
                <input
                  type="text"
                  placeholder="my-rg"
                  className="w-full px-3 py-2 border rounded-md"
                  value={azureContext.resourceGroup}
                  onChange={(e) =>
                    setAzureContext((p) => ({
                      ...p,
                      resourceGroup: e.target.value,
                    }))
                  }
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  AKS Arc Cluster
                </label>
                <input
                  type="text"
                  placeholder="my-cluster"
                  className="w-full px-3 py-2 border rounded-md"
                  value={azureContext.clusterName}
                  onChange={(e) =>
                    setAzureContext((p) => ({
                      ...p,
                      clusterName: e.target.value,
                    }))
                  }
                />
              </div>
              <p className="text-sm text-gray-500 bg-gray-50 p-2 rounded">
                💡 Run <code className="bg-gray-200 px-1">az account show</code>{" "}
                to find these values
              </p>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setAzureContext((p) => ({ ...p, connected: true }));
                  setShowConfig(false);
                }}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              >
                Connect
              </button>
              <button
                onClick={() => setShowConfig(false)}
                className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="max-w-6xl mx-auto p-6">
        {/* Connection warning */}
        {!azureContext.connected && (
          <div className="mb-6 p-4 bg-yellow-50 border border-yellow-300 rounded-lg flex items-center justify-between">
            <div>
              <p className="font-medium text-yellow-800">
                ⚠️ Not connected to Azure
              </p>
              <p className="text-sm text-yellow-700">
                Configure your Azure subscription and cluster to run real
                diagnostics
              </p>
            </div>
            <button
              onClick={() => setShowConfig(true)}
              className="px-4 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 text-sm"
            >
              Configure
            </button>
          </div>
        )}

        {azureContext.connected && !findings && (
          <div className="mb-6 p-4 bg-green-50 border border-green-300 rounded-lg">
            <p className="font-medium text-green-800">✅ Connected to Azure</p>
            <p className="text-sm text-green-700">
              <span className="font-mono">{azureContext.subscription}</span> |
              Cluster:{" "}
              <span className="font-mono">
                {azureContext.clusterName || "N/A"}
              </span>{" "}
              | RG:{" "}
              <span className="font-mono">
                {azureContext.resourceGroup || "N/A"}
              </span>
            </p>
          </div>
        )}

        {mode === "dashboard" && !findings && (
          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
              Run Diagnostics
            </h2>
            <div className="grid md:grid-cols-3 gap-6">
              {/* Environment Check Card */}
              <button
                onClick={() => runDiagnostic("envcheck")}
                disabled={!!running}
                className={`p-6 bg-white rounded-lg shadow-md hover:shadow-lg text-left border-2 ${running === "envcheck" ? "border-blue-500" : "border-transparent hover:border-blue-300"}`}
              >
                <div className="text-4xl mb-3">🖥️</div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Environment Check
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  Validate hardware, OS, drivers for Azure Local
                </p>
                <span
                  className={`inline-flex items-center px-4 py-2 rounded font-medium text-sm ${running === "envcheck" ? "bg-blue-100 text-blue-700" : "bg-blue-600 text-white"}`}
                >
                  {running === "envcheck" ? "⏳ Running..." : "Run Check"}
                </span>
              </button>

              {/* Egress Test Card */}
              <button
                onClick={() => runDiagnostic("egress")}
                disabled={!!running}
                className={`p-6 bg-white rounded-lg shadow-md hover:shadow-lg text-left border-2 ${running === "egress" ? "border-blue-500" : "border-transparent hover:border-blue-300"}`}
              >
                <div className="text-4xl mb-3">🌐</div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Egress Test
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  Test connectivity to Azure endpoints
                </p>
                <span
                  className={`inline-flex items-center px-4 py-2 rounded font-medium text-sm ${running === "egress" ? "bg-blue-100 text-blue-700" : "bg-blue-600 text-white"}`}
                >
                  {running === "egress" ? "⏳ Running..." : "Run Check"}
                </span>
              </button>

              {/* Cluster Validation Card */}
              <button
                onClick={() => runDiagnostic("validate")}
                disabled={!!running}
                className={`p-6 bg-white rounded-lg shadow-md hover:shadow-lg text-left border-2 ${running === "validate" ? "border-blue-500" : "border-transparent hover:border-blue-300"}`}
              >
                <div className="text-4xl mb-3">☸️</div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Cluster Validation
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  Check AKS Arc cluster health
                </p>
                <span
                  className={`inline-flex items-center px-4 py-2 rounded font-medium text-sm ${running === "validate" ? "bg-blue-100 text-blue-700" : "bg-blue-600 text-white"}`}
                >
                  {running === "validate" ? "⏳ Running..." : "Run Check"}
                </span>
              </button>
            </div>

            <div className="mt-8 p-6 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold text-blue-800 mb-2">
                💡 Tip: Chat Interface
              </h3>
              <p className="text-blue-700 text-sm">
                For natural language questions, use:{" "}
                <code className="bg-blue-100 px-2 py-1 rounded">
                  python -m agent.simple_chat
                </code>
              </p>
            </div>
          </div>
        )}

        {/* Results view - shown when findings exist */}
        {findings && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-800">Results</h2>
              <button
                onClick={() => setFindings(null)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                ← Back to Dashboard
              </button>
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
              <SummaryCard
                label="Total"
                value={findings.summary?.total ?? 0}
                color="bg-gray-500"
                active={filter === "all"}
                onClick={() => setFilter("all")}
              />
              <SummaryCard
                label="Passed"
                value={findings.summary?.pass ?? 0}
                color="bg-green-500"
                active={filter === "pass"}
                onClick={() => setFilter("pass")}
              />
              <SummaryCard
                label="Failed"
                value={findings.summary?.fail ?? 0}
                color="bg-red-500"
                active={filter === "fail"}
                onClick={() => setFilter("fail")}
              />
              <SummaryCard
                label="Warnings"
                value={findings.summary?.warn ?? 0}
                color="bg-yellow-500"
                active={filter === "warn"}
                onClick={() => setFilter("warn")}
              />
              <SummaryCard
                label="Skipped"
                value={findings.summary?.skipped ?? 0}
                color="bg-gray-400"
                active={filter === "skipped"}
                onClick={() => setFilter("skipped")}
              />
            </div>

            {/* Metadata */}
            <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Target:</span>{" "}
                  <span className="font-medium">{findings.target}</span>
                </div>
                <div>
                  <span className="text-gray-500">Run ID:</span>{" "}
                  <span className="font-mono text-xs">
                    {findings.runId ?? "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-gray-500">Time:</span>{" "}
                  <span>{new Date(findings.timestamp).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-gray-500">Version:</span>{" "}
                  <span>{findings.version}</span>
                </div>
              </div>
            </div>

            {/* Checks */}
            <div className="space-y-3">
              {filteredChecks.map((check) => (
                <CheckCard
                  key={check.id}
                  check={check}
                  expanded={expandedChecks.has(check.id)}
                  onToggle={() => toggleCheck(check.id)}
                />
              ))}
              {filteredChecks.length === 0 && (
                <p className="text-center text-gray-500 py-8">
                  No checks match the current filter.
                </p>
              )}
            </div>
          </div>
        )}

        {/* File drop zone for viewer mode */}
        {mode === "viewer" && !findings && (
          <div
            className={`drop-zone ${dragOver ? "drag-over" : ""}`}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
          >
            <div className="text-gray-500">
              <svg
                className="mx-auto h-12 w-12 mb-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              <p className="text-lg mb-2">Drop findings.json here</p>
              <p className="text-sm text-gray-400">or</p>
              <label className="mt-2 inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700">
                Browse Files
                <input
                  type="file"
                  accept=".json"
                  onChange={handleFileInput}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded text-red-700">
            {error}
          </div>
        )}
      </main>
    </div>
  );
}

interface SummaryCardProps {
  label: string;
  value: number;
  color: string;
  active: boolean;
  onClick: () => void;
}

function SummaryCard({
  label,
  value,
  color,
  active,
  onClick,
}: SummaryCardProps) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-lg text-white transition-all ${color} ${
        active
          ? "ring-2 ring-offset-2 ring-gray-900"
          : "opacity-80 hover:opacity-100"
      }`}
    >
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm opacity-90">{label}</div>
    </button>
  );
}

export default App;
