import {
  useState,
  useCallback,
  useEffect,
  type DragEvent,
  type ChangeEvent,
} from "react";
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

interface ClusterInfo {
  name: string;
  resourceGroup: string;
  location: string;
  connectivityStatus: string;
  provisioningState: string;
  kubernetesVersion: string;
  totalNodeCount: number;
}

interface AzureStatus {
  authenticated: boolean;
  azCliInstalled: boolean;
  subscription?: { id: string; name: string };
  user?: string;
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
  const [clusters, setClusters] = useState<ClusterInfo[]>([]);
  const [loadingClusters, setLoadingClusters] = useState(false);
  const [azureStatus, setAzureStatus] = useState<AzureStatus | null>(null);
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

  // MCP Server configuration
  const MCP_SERVER_URL = "http://127.0.0.1:8080";

  // Load real clusters from Azure
  const loadClusters = useCallback(async () => {
    setLoadingClusters(true);
    try {
      const response = await fetch(`${MCP_SERVER_URL}/api/clusters`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setClusters(data.clusters);
        }
      }
    } catch {
      console.log("Failed to load clusters");
    } finally {
      setLoadingClusters(false);
    }
  }, []);

  // Check Azure CLI status on mount
  const checkAzureStatus = useCallback(async () => {
    try {
      const response = await fetch(`${MCP_SERVER_URL}/api/status`);
      if (response.ok) {
        const status = await response.json();
        setAzureStatus(status);
        if (status.authenticated) {
          setAzureContext((prev) => ({
            ...prev,
            subscription: status.subscription?.name || "",
            subscriptionId: status.subscription?.id || "",
            connected: true,
          }));
          // Auto-load clusters if authenticated
          loadClusters();
        }
      }
    } catch {
      console.log("MCP server not reachable");
    }
  }, [loadClusters]);

  // Check Azure status on component mount
  useEffect(() => {
    checkAzureStatus();
  }, [checkAzureStatus]);

  // Environment Checker state
  const [checkerStatus, setCheckerStatus] = useState<{
    installed: boolean;
    path?: string;
    checking: boolean;
    installing: boolean;
  }>({ installed: false, checking: true, installing: false });

  // Check Environment Checker status
  const checkEnvChecker = useCallback(async () => {
    setCheckerStatus((prev) => ({ ...prev, checking: true }));
    try {
      const response = await fetch(
        `${MCP_SERVER_URL}/api/connectivity/checker-status`,
      );
      if (response.ok) {
        const status = await response.json();
        setCheckerStatus({
          installed: status.installed,
          path: status.path,
          checking: false,
          installing: false,
        });
      }
    } catch {
      setCheckerStatus((prev) => ({ ...prev, checking: false }));
    }
  }, []);

  // Install Environment Checker
  const installEnvChecker = useCallback(async () => {
    setCheckerStatus((prev) => ({ ...prev, installing: true }));
    setError(null);
    try {
      const response = await fetch(
        `${MCP_SERVER_URL}/api/connectivity/install-checker`,
        { method: "POST" },
      );
      const result = await response.json();
      if (result.success) {
        setCheckerStatus({
          installed: true,
          path: result.module?.Path,
          checking: false,
          installing: false,
        });
      } else {
        setError(result.error || "Failed to install Environment Checker");
        setCheckerStatus((prev) => ({ ...prev, installing: false }));
      }
    } catch (err) {
      setError("Failed to install Environment Checker");
      setCheckerStatus((prev) => ({ ...prev, installing: false }));
    }
  }, []);

  // Check on mount
  useEffect(() => {
    checkEnvChecker();
  }, [checkEnvChecker]);

  // Progress state for streaming
  const [progress, setProgress] = useState<{
    message: string;
    phase: string;
    checksProcessed: number;
  } | null>(null);

  const runDiagnostic = useCallback(
    async (type: "connectivity" | "validate") => {
      setRunning(type);
      setError(null);
      setProgress(null);

      try {
        // For connectivity check, use SSE streaming endpoint
        if (type === "connectivity") {
          // Use EventSource for SSE streaming
          const url = `${MCP_SERVER_URL}/api/connectivity/check/stream?mode=quick&install_checker=false`;
          const eventSource = new EventSource(url);

          return new Promise<void>((resolve, reject) => {
            // Handle status events
            eventSource.addEventListener("status", (event) => {
              const data = JSON.parse(event.data);
              setProgress({
                message: data.message,
                phase: data.phase || "running",
                checksProcessed: 0,
              });
            });

            // Handle progress events
            eventSource.addEventListener("progress", (event) => {
              const data = JSON.parse(event.data);
              setProgress((prev) => ({
                message: data.message,
                phase: prev?.phase || "running",
                checksProcessed:
                  data.checksProcessed || (prev?.checksProcessed || 0) + 1,
              }));
            });

            // Handle completion
            eventSource.addEventListener("complete", (event) => {
              const data = JSON.parse(event.data);
              eventSource.close();
              setProgress(null);

              if (data.success && data.findings) {
                setFindings(data.findings);
              }
              setRunning(null);
              resolve();
            });

            // Handle errors
            eventSource.addEventListener("error", (event) => {
              eventSource.close();
              setProgress(null);
              setRunning(null);
              // Check if it's a custom error event or connection error
              if (event instanceof MessageEvent) {
                const data = JSON.parse(event.data);
                reject(new Error(data.error || "Connectivity check failed"));
              } else {
                reject(new Error("Connection to server lost"));
              }
            });

            // Fallback: also listen for generic message if browser doesn't support custom events
            eventSource.onmessage = (event) => {
              try {
                const data = JSON.parse(event.data);
                if (data.type === "complete" && data.findings) {
                  eventSource.close();
                  setFindings(data.findings);
                  setProgress(null);
                  setRunning(null);
                  resolve();
                }
              } catch {
                // Ignore parse errors for keepalive messages
              }
            };

            // Handle connection errors
            eventSource.onerror = () => {
              // Don't immediately reject - might just be the stream ending
              setTimeout(() => {
                if (eventSource.readyState === EventSource.CLOSED) {
                  // Stream closed without complete event - fall back to non-streaming
                  eventSource.close();
                  setProgress({
                    message: "Falling back to non-streaming mode...",
                    phase: "fallback",
                    checksProcessed: 0,
                  });

                  // Fall back to regular endpoint
                  fetch(
                    `${MCP_SERVER_URL}/api/connectivity/check?mode=quick&install_checker=false`,
                  )
                    .then((res) => res.json())
                    .then((result) => {
                      if (result.success) {
                        setFindings(result.findings);
                      } else {
                        throw new Error(result.error || "Check failed");
                      }
                      setProgress(null);
                      setRunning(null);
                      resolve();
                    })
                    .catch((err) => {
                      setProgress(null);
                      setRunning(null);
                      reject(err);
                    });
                }
              }, 1000);
            };
          });
        }

        // For validate, use the cluster validation API
        if (
          type === "validate" &&
          azureContext.clusterName &&
          azureContext.resourceGroup
        ) {
          const response = await fetch(
            `${MCP_SERVER_URL}/api/cluster/${encodeURIComponent(azureContext.clusterName)}/validate?resource_group=${encodeURIComponent(azureContext.resourceGroup)}`,
          );

          if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
          }

          const result = await response.json();

          if (!result.success) {
            throw new Error(result.error || "Validation failed");
          }

          // Convert API response to Findings format
          const validationFindings: Findings = {
            version: "1.0.0",
            target: "cluster",
            timestamp: new Date().toISOString(),
            runId: `validate-${Date.now()}`,
            checks: result.checks.map(
              (check: {
                id: string;
                title: string;
                status: string;
                severity: string;
                evidence?: Record<string, unknown>;
                hint?: string;
              }) => ({
                id: check.id,
                title: check.title,
                status: check.status as "pass" | "fail" | "warn" | "skipped",
                severity: check.severity as "high" | "medium" | "low",
                description: check.hint || `${check.title} check`,
                evidence: check.evidence,
              }),
            ),
            summary: result.summary,
            metadata: {
              cluster: result.cluster,
              resourceGroup: result.resourceGroup,
            },
          };

          setFindings(validationFindings);
          setRunning(null);
          return;
        }

        // Fallback - shouldn't reach here
        throw new Error("Invalid diagnostic type or missing parameters");
      } catch (err) {
        console.error("Diagnostic error:", err);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to run diagnostic. Is the MCP server running?",
        );
        setRunning(null);
      }
    },
    [azureContext],
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
            className="bg-white rounded-lg shadow-xl p-6 w-full max-w-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-xl font-bold mb-4">Azure Connection</h2>

            {/* Azure Status */}
            <div
              className={`mb-4 p-3 rounded-lg ${azureStatus?.authenticated ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}
            >
              {azureStatus?.authenticated ? (
                <>
                  <p className="font-medium text-green-800">
                    ✅ Azure CLI Authenticated
                  </p>
                  <p className="text-sm text-green-700">
                    Subscription:{" "}
                    <span className="font-mono">
                      {azureStatus.subscription?.name}
                    </span>
                  </p>
                  <p className="text-sm text-green-700">
                    User: {azureStatus.user}
                  </p>
                </>
              ) : (
                <>
                  <p className="font-medium text-red-800">
                    ❌ Not authenticated
                  </p>
                  <p className="text-sm text-red-700">
                    Run <code className="bg-gray-200 px-1">az login</code> and
                    restart MCP server
                  </p>
                </>
              )}
            </div>

            {/* Cluster Selection */}
            {clusters.length > 0 ? (
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700">
                  Select AKS Arc Cluster ({clusters.length} available)
                </label>
                <div className="max-h-64 overflow-y-auto border rounded-lg">
                  {clusters.map((cluster) => (
                    <div
                      key={`${cluster.name}-${cluster.resourceGroup}`}
                      onClick={() => {
                        setAzureContext((prev) => ({
                          ...prev,
                          clusterName: cluster.name,
                          resourceGroup: cluster.resourceGroup,
                        }));
                      }}
                      className={`p-3 border-b cursor-pointer hover:bg-blue-50 ${
                        azureContext.clusterName === cluster.name
                          ? "bg-blue-100"
                          : ""
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{cluster.name}</span>
                        <span
                          className={`text-xs px-2 py-1 rounded ${
                            cluster.connectivityStatus === "Connected"
                              ? "bg-green-100 text-green-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {cluster.connectivityStatus}
                        </span>
                      </div>
                      <div className="text-sm text-gray-500">
                        RG: {cluster.resourceGroup} | K8s:{" "}
                        {cluster.kubernetesVersion} | Nodes:{" "}
                        {cluster.totalNodeCount}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : loadingClusters ? (
              <div className="text-center py-4">
                <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-2"></div>
                <p className="text-gray-600">Loading clusters from Azure...</p>
              </div>
            ) : (
              <div className="text-center py-4 bg-gray-50 rounded-lg">
                <p className="text-gray-600">No clusters found</p>
                <button
                  onClick={loadClusters}
                  className="mt-2 text-blue-600 hover:underline text-sm"
                >
                  Retry
                </button>
              </div>
            )}

            {/* Selected cluster info */}
            {azureContext.clusterName && (
              <div className="mt-4 p-3 bg-blue-50 rounded-lg">
                <p className="text-sm font-medium text-blue-800">Selected:</p>
                <p className="text-sm text-blue-700">
                  Cluster:{" "}
                  <span className="font-mono">{azureContext.clusterName}</span>
                </p>
                <p className="text-sm text-blue-700">
                  Resource Group:{" "}
                  <span className="font-mono">
                    {azureContext.resourceGroup}
                  </span>
                </p>
              </div>
            )}

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setAzureContext((p) => ({ ...p, connected: true }));
                  setShowConfig(false);
                }}
                disabled={!azureContext.clusterName}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                Use Selected Cluster
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
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-green-800">
                  ✅ Connected to Azure via MCP Server
                </p>
                <p className="text-sm text-green-700">
                  User:{" "}
                  <span className="font-mono">
                    {azureStatus?.user || "N/A"}
                  </span>{" "}
                  | Subscription:{" "}
                  <span className="font-mono">{azureContext.subscription}</span>
                </p>
                {azureContext.clusterName && (
                  <p className="text-sm text-green-700 mt-1">
                    Selected Cluster:{" "}
                    <span className="font-mono font-semibold">
                      {azureContext.clusterName}
                    </span>{" "}
                    ({azureContext.resourceGroup})
                  </p>
                )}
              </div>
              <button
                onClick={() => setShowConfig(true)}
                className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
              >
                Change Cluster
              </button>
            </div>
          </div>
        )}

        {mode === "dashboard" && !findings && (
          <div>
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
              Run Diagnostics
            </h2>

            {/* Environment Checker Status Banner */}
            <div
              className={`mb-6 p-4 rounded-lg border ${
                checkerStatus.installed
                  ? "bg-green-50 border-green-200"
                  : "bg-yellow-50 border-yellow-200"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p
                    className={`font-medium ${checkerStatus.installed ? "text-green-800" : "text-yellow-800"}`}
                  >
                    {checkerStatus.checking
                      ? "🔄 Checking Environment Checker status..."
                      : checkerStatus.installed
                        ? "✅ Microsoft Environment Checker installed"
                        : "⚠️ Microsoft Environment Checker not installed"}
                  </p>
                  <p
                    className={`text-sm ${checkerStatus.installed ? "text-green-700" : "text-yellow-700"}`}
                  >
                    {checkerStatus.installed
                      ? "Using official Microsoft tool for comprehensive checks"
                      : "Install for comprehensive host validation (optional)"}
                  </p>
                </div>
                {!checkerStatus.installed && !checkerStatus.checking && (
                  <button
                    onClick={installEnvChecker}
                    disabled={checkerStatus.installing}
                    className={`px-4 py-2 rounded text-sm font-medium ${
                      checkerStatus.installing
                        ? "bg-gray-400 cursor-wait"
                        : "bg-yellow-600 hover:bg-yellow-700 text-white"
                    }`}
                  >
                    {checkerStatus.installing
                      ? "⏳ Installing..."
                      : "Install Now"}
                  </button>
                )}
              </div>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Unified Connectivity Check Card */}
              <div
                className={`p-6 bg-white rounded-lg shadow-md text-left border-2 ${
                  running === "connectivity"
                    ? "border-blue-500"
                    : "border-transparent hover:border-blue-300 hover:shadow-lg"
                }`}
              >
                <div className="text-4xl mb-3">🌐</div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Connectivity Check
                </h3>
                <p className="text-sm text-gray-600 mb-2">
                  DNS, TLS, and Azure endpoint reachability
                </p>

                <div className="text-xs text-gray-500 mb-4">
                  <p>✓ Tests 50+ required Azure endpoints</p>
                  <p>✓ Validates DNS resolution & TLS certificates</p>
                  <p>
                    ✓{" "}
                    {checkerStatus.installed
                      ? "Uses Microsoft Environment Checker"
                      : "Requires Microsoft Environment Checker"}
                  </p>
                </div>

                {/* Progress display when running */}
                {running === "connectivity" && progress && (
                  <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                      <span className="text-sm font-medium text-blue-700">
                        {progress.phase}
                      </span>
                    </div>
                    <p className="text-xs text-blue-600 truncate">
                      {progress.message}
                    </p>
                    {progress.checksProcessed > 0 && (
                      <p className="text-xs text-blue-500 mt-1">
                        {progress.checksProcessed} checks processed...
                      </p>
                    )}
                  </div>
                )}

                <button
                  onClick={() => runDiagnostic("connectivity")}
                  disabled={!!running}
                  className={`inline-flex items-center px-4 py-2 rounded font-medium text-sm ${
                    running === "connectivity"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {running === "connectivity"
                    ? "⏳ Running..."
                    : "Run Connectivity Check"}
                </button>
              </div>

              {/* Cluster Validation Card */}
              <div
                className={`p-6 bg-white rounded-lg shadow-md text-left border-2 ${
                  !azureContext.clusterName
                    ? "border-orange-300 bg-orange-50"
                    : running === "validate"
                      ? "border-blue-500"
                      : "border-transparent hover:border-blue-300 hover:shadow-lg"
                }`}
              >
                <div className="text-4xl mb-3">☸️</div>
                <h3 className="text-lg font-semibold text-gray-800 mb-2">
                  Cluster Validation
                </h3>
                <p className="text-sm text-gray-600 mb-2">
                  Check AKS Arc cluster health
                </p>

                {/* Cluster selector */}
                {clusters.length > 0 ? (
                  <div className="mb-4">
                    <label className="block text-xs text-gray-500 mb-1">
                      Select cluster to validate:
                    </label>
                    <select
                      value={
                        azureContext.clusterName
                          ? `${azureContext.clusterName}|${azureContext.resourceGroup}`
                          : ""
                      }
                      onChange={(e) => {
                        if (e.target.value) {
                          const [name, rg] = e.target.value.split("|");
                          setAzureContext((prev) => ({
                            ...prev,
                            clusterName: name,
                            resourceGroup: rg,
                          }));
                        } else {
                          setAzureContext((prev) => ({
                            ...prev,
                            clusterName: "",
                            resourceGroup: "",
                          }));
                        }
                      }}
                      className="w-full px-2 py-1 text-sm border rounded bg-white"
                    >
                      <option value="">-- Select a cluster --</option>
                      {clusters.map((c) => (
                        <option
                          key={`${c.name}-${c.resourceGroup}`}
                          value={`${c.name}|${c.resourceGroup}`}
                        >
                          {c.name} (
                          {c.connectivityStatus === "Connected" ? "🟢" : "🔴"}{" "}
                          {c.kubernetesVersion})
                        </option>
                      ))}
                    </select>
                  </div>
                ) : (
                  <p className="text-xs text-orange-600 mb-4">
                    ⚠️ No clusters loaded. Check MCP server connection.
                  </p>
                )}

                <button
                  onClick={() => runDiagnostic("validate")}
                  disabled={!!running || !azureContext.clusterName}
                  className={`inline-flex items-center px-4 py-2 rounded font-medium text-sm ${
                    !azureContext.clusterName
                      ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                      : running === "validate"
                        ? "bg-blue-100 text-blue-700"
                        : "bg-blue-600 text-white hover:bg-blue-700"
                  }`}
                >
                  {running === "validate"
                    ? "⏳ Running..."
                    : !azureContext.clusterName
                      ? "Select cluster first"
                      : `Validate ${azureContext.clusterName}`}
                </button>
              </div>
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
              <div>
                <h2 className="text-xl font-bold text-gray-800">Results</h2>
                {findings.metadata && "cluster" in findings.metadata && (
                  <p className="text-sm text-gray-600">
                    Cluster:{" "}
                    <span className="font-mono font-semibold">
                      {findings.metadata["cluster"] as string}
                    </span>
                    {"resourceGroup" in findings.metadata && (
                      <span>
                        {" "}
                        ({findings.metadata["resourceGroup"] as string})
                      </span>
                    )}
                  </p>
                )}
              </div>
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
