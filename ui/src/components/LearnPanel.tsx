import { useState, useEffect } from "react";

interface Topic {
  id: string;
  title: string;
  description: string;
}

interface TopicContent {
  type: string;
  topic: string;
  title: string;
  description: string;
  content: string;
  links: Array<{ title: string; url: string }>;
  related_topics: string[];
}

interface LearnPanelProps {
  serverUrl: string;
  onClose?: () => void;
}

export function LearnPanel({ serverUrl, onClose }: LearnPanelProps) {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [content, setContent] = useState<TopicContent | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load topics on mount
  useEffect(() => {
    loadTopics();
  }, [serverUrl]);

  const loadTopics = async () => {
    setError(null);
    try {
      const response = await fetch(`${serverUrl}/mcp/tools/arcops.explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arguments: { topic: "list" } }),
      });

      if (!response.ok) {
        setError(`Server error: ${response.status}`);
        return;
      }

      const data = await response.json();
      console.log("LearnPanel topics response:", data);

      // Handle both wrapped and unwrapped response formats
      const result = data.result || data;
      if (result?.topics) {
        setTopics(result.topics);
      } else if (result?.success === false) {
        setError(result.error || "Failed to load topics");
      } else {
        setError("No topics found in response");
      }
    } catch (err) {
      console.error("Failed to load topics:", err);
      setError(err instanceof Error ? err.message : "Network error");
    }
  };

  const loadTopicContent = async (topicId: string) => {
    setLoading(true);
    setError(null);
    setSelectedTopic(topicId);

    try {
      const response = await fetch(`${serverUrl}/mcp/tools/arcops.explain`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arguments: { topic: topicId } }),
      });
      const data = await response.json();
      // Handle both wrapped and unwrapped response formats
      const result = data.result || data;
      if (result?.content) {
        setContent(result);
      } else if (result?.success === false) {
        setError(result.error || "Failed to load content");
      } else {
        setError(data.error || "Failed to load content");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error");
    } finally {
      setLoading(false);
    }
  };

  // Simple markdown-like rendering for content
  const renderContent = (text: string) => {
    const lines = text.split("\n");
    return lines.map((line, i) => {
      // Headers
      if (line.startsWith("## ")) {
        return (
          <h2 key={i} className="text-xl font-bold text-gray-800 mt-6 mb-3">
            {line.slice(3)}
          </h2>
        );
      }
      if (line.startsWith("### ")) {
        return (
          <h3 key={i} className="text-lg font-semibold text-gray-700 mt-4 mb-2">
            {line.slice(4)}
          </h3>
        );
      }
      // List items
      if (line.startsWith("- ")) {
        return (
          <li key={i} className="ml-4 text-gray-600">
            {line.slice(2)}
          </li>
        );
      }
      // Numbered list
      if (/^\d+\.\s/.test(line)) {
        const match = line.match(/^(\d+)\.\s(.*)$/);
        if (match) {
          return (
            <li key={i} className="ml-4 text-gray-600 list-decimal">
              <strong>{match[2].split(":")[0]}</strong>
              {match[2].includes(":")
                ? ":" + match[2].split(":").slice(1).join(":")
                : ""}
            </li>
          );
        }
      }
      // Bold text
      if (line.includes("**")) {
        const parts = line.split(/\*\*(.*?)\*\*/g);
        return (
          <p key={i} className="text-gray-600 my-1">
            {parts.map((part, j) =>
              j % 2 === 1 ? (
                <strong key={j} className="text-gray-800">
                  {part}
                </strong>
              ) : (
                part
              ),
            )}
          </p>
        );
      }
      // Empty lines
      if (line.trim() === "") {
        return <div key={i} className="h-2" />;
      }
      // Regular paragraph
      return (
        <p key={i} className="text-gray-600 my-1">
          {line}
        </p>
      );
    });
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-emerald-600 to-teal-700 text-white">
        <div className="flex items-center gap-2">
          <span className="text-xl">📚</span>
          <div>
            <h3 className="font-semibold">Learn Azure Local & AKS Arc</h3>
            <p className="text-xs text-emerald-100">Educational Resources</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 hover:bg-white/20 rounded transition-colors"
            aria-label="Close panel"
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

      <div className="flex-1 flex overflow-hidden">
        {/* Topic sidebar */}
        <div className="w-64 border-r border-gray-200 overflow-y-auto bg-gray-50">
          <div className="p-3">
            <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Topics
            </h4>
            <div className="space-y-1">
              {topics.length === 0 && !error && (
                <div className="flex items-center gap-2 text-gray-400 text-sm p-2">
                  <div className="animate-spin h-4 w-4 border-2 border-gray-400 border-t-transparent rounded-full" />
                  Loading...
                </div>
              )}
              {topics.length === 0 && error && (
                <div className="text-red-500 text-sm p-2">
                  <p className="font-medium">Failed to load</p>
                  <p className="text-xs mt-1">{error}</p>
                  <button
                    onClick={loadTopics}
                    className="mt-2 text-xs text-blue-600 hover:underline"
                  >
                    Retry
                  </button>
                </div>
              )}
              {topics.map((topic) => (
                <button
                  key={topic.id}
                  onClick={() => loadTopicContent(topic.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    selectedTopic === topic.id
                      ? "bg-emerald-100 text-emerald-800 font-medium"
                      : "text-gray-700 hover:bg-gray-100"
                  }`}
                >
                  {topic.title}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin h-8 w-8 border-4 border-emerald-500 border-t-transparent rounded-full" />
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
              {error}
            </div>
          ) : content ? (
            <div>
              {/* Title */}
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                {content.title}
              </h1>
              <p className="text-gray-500 mb-6">{content.description}</p>

              {/* Content */}
              <div className="prose prose-sm max-w-none">
                {renderContent(content.content)}
              </div>

              {/* Links */}
              {content.links && content.links.length > 0 && (
                <div className="mt-8 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h4 className="font-semibold text-blue-800 mb-3">
                    📎 Official Documentation
                  </h4>
                  <ul className="space-y-2">
                    {content.links.map((link, i) => (
                      <li key={i}>
                        <a
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline text-sm flex items-center gap-2"
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
                              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                            />
                          </svg>
                          {link.title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Related topics */}
              {content.related_topics && content.related_topics.length > 0 && (
                <div className="mt-6">
                  <h4 className="text-sm font-medium text-gray-500 mb-2">
                    Related Topics
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {content.related_topics.map((topicId) => {
                      const topic = topics.find((t) => t.id === topicId);
                      return topic ? (
                        <button
                          key={topicId}
                          onClick={() => loadTopicContent(topicId)}
                          className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm hover:bg-gray-200 transition-colors"
                        >
                          {topic.title}
                        </button>
                      ) : null;
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-500">
              <span className="text-4xl mb-4">📖</span>
              <p className="text-lg font-medium">Select a topic to learn</p>
              <p className="text-sm">
                Choose from the topics on the left to get started
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LearnPanel;
