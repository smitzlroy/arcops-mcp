import { useState, useCallback, useEffect } from "react";
import { ChatPanel } from "./components/ChatPanel";

interface AzureStatus {
  authenticated: boolean;
  azCliInstalled: boolean;
  subscription?: { id: string; name: string };
  user?: string;
}

/**
 * Simplified ArcOps MCP UI - Chat-First Design
 *
 * The main interface is the chat panel where users can:
 * - Describe issues in natural language
 * - Get diagnostic tools automatically invoked
 * - View results inline in the conversation
 */
function App() {
  const [azureStatus, setAzureStatus] = useState<AzureStatus | null>(null);
  const [azureStatusLoading, setAzureStatusLoading] = useState(true);
  const [serverReachable, setServerReachable] = useState<boolean | null>(null);

  // MCP Server URL - defaults to local development
  const MCP_SERVER_URL =
    import.meta.env.VITE_MCP_SERVER_URL || "http://127.0.0.1:8080";

  // Check Azure CLI status on mount
  const checkAzureStatus = useCallback(async () => {
    console.log("[Azure] Checking status at", MCP_SERVER_URL);
    setAzureStatusLoading(true);
    try {
      const response = await fetch(`${MCP_SERVER_URL}/api/status`, {
        signal: AbortSignal.timeout(10000),
      });
      setServerReachable(true);
      if (response.ok) {
        const status = await response.json();
        console.log("[Azure] Status received:", status);
        setAzureStatus(status);
      }
    } catch (err) {
      console.log("[Azure] MCP server not reachable:", err);
      setServerReachable(false);
    } finally {
      setAzureStatusLoading(false);
    }
  }, [MCP_SERVER_URL]);

  useEffect(() => {
    checkAzureStatus();
  }, [checkAzureStatus]);

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {/* Compact Header */}
      <header className="bg-gray-900 text-white py-2 px-4 shadow-lg flex-shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-bold">ArcOps MCP</h1>
            <span className="text-gray-400 text-sm hidden sm:inline">
              Azure Local & AKS Arc Diagnostics
            </span>
          </div>

          {/* Status indicators */}
          <div className="flex items-center gap-3">
            {/* Server status */}
            <div className="flex items-center gap-2 text-sm">
              <span
                className={`w-2 h-2 rounded-full ${
                  serverReachable === null
                    ? "bg-gray-400"
                    : serverReachable
                      ? "bg-green-400"
                      : "bg-red-400"
                }`}
              />
              <span className="text-gray-300 hidden sm:inline">
                {serverReachable === null
                  ? "Connecting..."
                  : serverReachable
                    ? "Server"
                    : "Server Offline"}
              </span>
            </div>

            {/* Azure status */}
            <div
              className={`flex items-center gap-2 px-2 py-1 rounded text-sm ${
                azureStatusLoading
                  ? "text-blue-400"
                  : azureStatus?.authenticated
                    ? "text-green-400"
                    : "text-yellow-400"
              }`}
            >
              {azureStatusLoading ? (
                <>
                  <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  <span className="hidden sm:inline">Checking Azure...</span>
                </>
              ) : (
                <>
                  <span
                    className={`w-2 h-2 rounded-full ${
                      azureStatus?.authenticated
                        ? "bg-green-400"
                        : "bg-yellow-400"
                    }`}
                  />
                  <span className="hidden sm:inline">
                    {azureStatus?.authenticated
                      ? azureStatus.subscription?.name || "Azure Connected"
                      : "Azure Not Connected"}
                  </span>
                </>
              )}
            </div>

            {/* Help button */}
            <button
              onClick={() => {
                window.open(
                  "https://github.com/your-repo/arcops-mcp#readme",
                  "_blank",
                );
              }}
              className="p-1.5 hover:bg-gray-700 rounded transition-colors"
              title="Documentation"
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
                  d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Full height chat */}
      <main className="flex-1 overflow-hidden p-4">
        <div className="h-full max-w-4xl mx-auto">
          <ChatPanel serverUrl={MCP_SERVER_URL} />
        </div>
      </main>

      {/* Minimal footer with status */}
      <footer className="bg-gray-800 text-gray-400 text-xs py-1 px-4 flex-shrink-0">
        <div className="flex items-center justify-between">
          <span>{azureStatus?.user && `Signed in as ${azureStatus.user}`}</span>
          <span>MCP Server: {MCP_SERVER_URL}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
