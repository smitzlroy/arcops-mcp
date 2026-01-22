import { ChatPanel } from "./components/ChatPanel";

/**
 * Simplified ArcOps MCP UI - Chat-First Design
 *
 * The main interface is the chat panel where users can:
 * - Describe issues in natural language
 * - Get diagnostic tools automatically invoked
 * - View results inline in the conversation
 */
function App() {
  // MCP Server URL - defaults to local development
  const MCP_SERVER_URL =
    import.meta.env.VITE_MCP_SERVER_URL || "http://127.0.0.1:8085";

  return (
    <div className="h-screen flex flex-col bg-gray-900">
      {/* Full screen chat - no padding */}
      <main className="flex-1 overflow-hidden">
        <ChatPanel serverUrl={MCP_SERVER_URL} />
      </main>
    </div>
  );
}

export default App;
