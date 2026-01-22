import { useEffect, useState } from "react";

interface Tool {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: "idle" | "active" | "success" | "error";
}

interface ArchitectureDiagramProps {
  serverUrl: string;
  activeTools?: string[];
  onToolClick?: (toolId: string) => void;
}

// Azure Arc Jumpstart color palette
const COLORS = {
  background: "#1a1a2e",
  surface: "#16213e",
  surfaceLight: "#1f2b47",
  primary: "#0078d4", // Azure Blue
  secondary: "#50e6ff", // Azure Cyan
  accent: "#8661c5", // Purple
  success: "#57a773",
  warning: "#ffc107",
  error: "#e74856",
  text: "#ffffff",
  textMuted: "#8b949e",
  border: "#30363d",
  glow: "rgba(80, 230, 255, 0.3)",
};

const TOOLS: Tool[] = [
  {
    id: "arc.connectivity.check",
    name: "Connectivity Check",
    description: "Test Azure endpoint reachability",
    icon: "🌐",
    status: "idle",
  },
  {
    id: "aks.arc.validate",
    name: "Cluster Validation",
    description: "Validate AKS Arc cluster health",
    icon: "☸️",
    status: "idle",
  },
  {
    id: "aksarc.support.diagnose",
    name: "Known Issues",
    description: "Check for known AKS Arc issues",
    icon: "🔍",
    status: "idle",
  },
  {
    id: "aksarc.logs.collect",
    name: "Log Collection",
    description: "Collect AKS Arc diagnostic logs",
    icon: "📋",
    status: "idle",
  },
  {
    id: "azlocal.tsg.search",
    name: "TSG Search",
    description: "Search troubleshooting guides",
    icon: "📚",
    status: "idle",
  },
  {
    id: "arcops.diagnostics.bundle",
    name: "Diagnostic Bundle",
    description: "Create support bundle",
    icon: "📦",
    status: "idle",
  },
];

export function ArchitectureDiagram({
  activeTools = [],
  onToolClick,
}: ArchitectureDiagramProps) {
  const [tools, setTools] = useState<Tool[]>(TOOLS);
  const [animatingConnections, setAnimatingConnections] = useState<string[]>(
    [],
  );

  useEffect(() => {
    // Update tool statuses based on active tools
    setTools((prev) =>
      prev.map((tool) => ({
        ...tool,
        status: activeTools.includes(tool.id) ? "active" : "idle",
      })),
    );

    // Trigger connection animations
    if (activeTools.length > 0) {
      setAnimatingConnections(activeTools);
    }
  }, [activeTools]);

  return (
    <div
      className="relative w-full h-full min-h-[500px] overflow-hidden rounded-xl"
      style={{ background: COLORS.background }}
    >
      {/* Background grid pattern */}
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `
            linear-gradient(${COLORS.border} 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.border} 1px, transparent 1px)
          `,
          backgroundSize: "40px 40px",
        }}
      />

      {/* SVG for connection lines */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none">
        <defs>
          {/* Gradient for active connections */}
          <linearGradient
            id="connectionGradient"
            x1="0%"
            y1="0%"
            x2="100%"
            y2="0%"
          >
            <stop offset="0%" stopColor={COLORS.primary} />
            <stop offset="100%" stopColor={COLORS.secondary} />
          </linearGradient>

          {/* Animated dash pattern */}
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Connection lines from MCP Server to Tools */}
        {tools.map((tool, index) => {
          const isActive = animatingConnections.includes(tool.id);
          const startX = 200;
          const startY = 250;
          const endX = 400 + (index % 3) * 160;
          const endY = 100 + Math.floor(index / 3) * 200;

          // Create curved path
          const controlX1 = startX + 100;
          const controlY1 = startY;
          const controlX2 = endX - 50;
          const controlY2 = endY;

          return (
            <g key={tool.id}>
              {/* Base connection line */}
              <path
                d={`M ${startX} ${startY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${endX} ${endY}`}
                fill="none"
                stroke={COLORS.border}
                strokeWidth="2"
                opacity="0.5"
              />

              {/* Animated connection when active */}
              {isActive && (
                <path
                  d={`M ${startX} ${startY} C ${controlX1} ${controlY1}, ${controlX2} ${controlY2}, ${endX} ${endY}`}
                  fill="none"
                  stroke="url(#connectionGradient)"
                  strokeWidth="3"
                  strokeDasharray="10,5"
                  filter="url(#glow)"
                  className="animate-dash"
                />
              )}
            </g>
          );
        })}

        {/* Connections to Azure Local & AKS Arc */}
        <path
          d="M 720 150 L 850 100"
          fill="none"
          stroke={COLORS.border}
          strokeWidth="2"
          opacity="0.5"
        />
        <path
          d="M 720 350 L 850 400"
          fill="none"
          stroke={COLORS.border}
          strokeWidth="2"
          opacity="0.5"
        />
      </svg>

      {/* MCP Server Node */}
      <div
        className="absolute left-8 top-1/2 -translate-y-1/2 w-40"
        style={{ left: "80px", top: "220px" }}
      >
        <div
          className="relative p-4 rounded-xl border-2 text-center transition-all duration-300"
          style={{
            background: `linear-gradient(135deg, ${COLORS.surface}, ${COLORS.surfaceLight})`,
            borderColor: COLORS.primary,
            boxShadow: `0 0 30px ${COLORS.glow}`,
          }}
        >
          <div
            className="w-16 h-16 mx-auto mb-2 rounded-xl flex items-center justify-center text-3xl"
            style={{ background: COLORS.primary }}
          >
            🔌
          </div>
          <h3 className="font-bold text-white text-sm">MCP Server</h3>
          <p className="text-xs mt-1" style={{ color: COLORS.textMuted }}>
            ArcOps Bridge
          </p>
          <div className="mt-2 flex items-center justify-center gap-1">
            <div
              className="w-2 h-2 rounded-full animate-pulse"
              style={{ background: COLORS.success }}
            />
            <span className="text-xs" style={{ color: COLORS.success }}>
              Online
            </span>
          </div>
        </div>
      </div>

      {/* Tools Grid */}
      <div
        className="absolute"
        style={{ left: "280px", top: "40px", width: "400px" }}
      >
        <h4
          className="text-xs font-semibold mb-3 uppercase tracking-wider"
          style={{ color: COLORS.textMuted }}
        >
          Available Skills / Tools
        </h4>
        <div className="grid grid-cols-3 gap-3">
          {tools.map((tool) => (
            <button
              key={tool.id}
              onClick={() => onToolClick?.(tool.id)}
              className="relative p-3 rounded-lg border transition-all duration-300 text-left hover:scale-105"
              style={{
                background:
                  tool.status === "active"
                    ? `linear-gradient(135deg, ${COLORS.primary}40, ${COLORS.secondary}20)`
                    : COLORS.surface,
                borderColor:
                  tool.status === "active" ? COLORS.secondary : COLORS.border,
                boxShadow:
                  tool.status === "active" ? `0 0 20px ${COLORS.glow}` : "none",
              }}
            >
              {/* Status indicator */}
              {tool.status === "active" && (
                <div
                  className="absolute -top-1 -right-1 w-3 h-3 rounded-full animate-ping"
                  style={{ background: COLORS.secondary }}
                />
              )}

              <div className="text-2xl mb-1">{tool.icon}</div>
              <h5 className="text-xs font-medium text-white truncate">
                {tool.name}
              </h5>
              <p
                className="text-xs truncate mt-0.5"
                style={{ color: COLORS.textMuted }}
              >
                {tool.description}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Azure Local Node */}
      <div className="absolute" style={{ right: "40px", top: "60px" }}>
        <div
          className="p-4 rounded-xl border text-center"
          style={{
            background: COLORS.surface,
            borderColor: COLORS.accent,
          }}
        >
          <div
            className="w-14 h-14 mx-auto mb-2 rounded-xl flex items-center justify-center"
            style={{ background: COLORS.accent }}
          >
            <svg className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <h3 className="font-bold text-white text-sm">Azure Local</h3>
          <p className="text-xs mt-1" style={{ color: COLORS.textMuted }}>
            On-premises
          </p>
        </div>
      </div>

      {/* AKS Arc Node */}
      <div className="absolute" style={{ right: "40px", bottom: "60px" }}>
        <div
          className="p-4 rounded-xl border text-center"
          style={{
            background: COLORS.surface,
            borderColor: COLORS.primary,
          }}
        >
          <div
            className="w-14 h-14 mx-auto mb-2 rounded-xl flex items-center justify-center"
            style={{ background: COLORS.primary }}
          >
            <svg className="w-8 h-8 text-white" viewBox="0 0 24 24" fill="none">
              <circle
                cx="12"
                cy="12"
                r="3"
                stroke="currentColor"
                strokeWidth="2"
              />
              <circle
                cx="12"
                cy="12"
                r="8"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path
                d="M12 4v4M12 16v4M4 12h4M16 12h4"
                stroke="currentColor"
                strokeWidth="2"
              />
            </svg>
          </div>
          <h3 className="font-bold text-white text-sm">AKS Arc</h3>
          <p className="text-xs mt-1" style={{ color: COLORS.textMuted }}>
            Kubernetes
          </p>
        </div>
      </div>

      {/* Legend */}
      <div
        className="absolute bottom-4 left-4 flex items-center gap-4 text-xs"
        style={{ color: COLORS.textMuted }}
      >
        <div className="flex items-center gap-1">
          <div className="w-8 h-0.5" style={{ background: COLORS.border }} />
          <span>Connection</span>
        </div>
        <div className="flex items-center gap-1">
          <div
            className="w-8 h-0.5"
            style={{
              background: `linear-gradient(90deg, ${COLORS.primary}, ${COLORS.secondary})`,
            }}
          />
          <span>Active</span>
        </div>
        <div className="flex items-center gap-1">
          <div
            className="w-2 h-2 rounded-full animate-pulse"
            style={{ background: COLORS.success }}
          />
          <span>Online</span>
        </div>
      </div>

      {/* CSS for dash animation */}
      <style>{`
        @keyframes dash {
          to {
            stroke-dashoffset: -30;
          }
        }
        .animate-dash {
          animation: dash 0.5s linear infinite;
        }
      `}</style>
    </div>
  );
}

export default ArchitectureDiagram;
