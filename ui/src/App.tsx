import { useState, useCallback, type DragEvent, type ChangeEvent } from 'react';
import { type Findings, type Check, validateFindings, calculateSummary } from './lib/schema';
import CheckCard from './components/CheckCard';

function App() {
  const [findings, setFindings] = useState<Findings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedChecks, setExpandedChecks] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<Check['status'] | 'all'>('all');

  const loadFindings = useCallback((data: unknown) => {
    if (validateFindings(data)) {
      // Calculate summary if not provided
      if (!data.summary) {
        data.summary = calculateSummary(data.checks);
      }
      setFindings(data);
      setError(null);
    } else {
      setError('Invalid findings format. Please ensure the file matches the schema.');
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
          setError('Failed to parse JSON file.');
        }
      };
      reader.onerror = () => setError('Failed to read file.');
      reader.readAsText(file);
    },
    [loadFindings]
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
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
    [handleFile]
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
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `findings-${findings.runId ?? 'export'}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [findings]);

  const filteredChecks =
    findings?.checks.filter((c) => filter === 'all' || c.status === filter) ?? [];

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-gray-900 text-white py-4 px-6 shadow-lg">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">ArcOps MCP</h1>
            <p className="text-gray-400 text-sm">Findings Report Viewer</p>
          </div>
          {findings && (
            <button
              onClick={exportBundle}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm font-medium transition-colors"
            >
              Export Evidence Pack
            </button>
          )}
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6">
        {!findings ? (
          /* Drop zone */
          <div
            className={`drop-zone ${dragOver ? 'drag-over' : ''}`}
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
              <label className="mt-2 inline-block px-4 py-2 bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700 transition-colors">
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
        ) : (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
              <SummaryCard
                label="Total"
                value={findings.summary?.total ?? 0}
                color="bg-gray-500"
                active={filter === 'all'}
                onClick={() => setFilter('all')}
              />
              <SummaryCard
                label="Passed"
                value={findings.summary?.pass ?? 0}
                color="bg-pass"
                active={filter === 'pass'}
                onClick={() => setFilter('pass')}
              />
              <SummaryCard
                label="Failed"
                value={findings.summary?.fail ?? 0}
                color="bg-fail"
                active={filter === 'fail'}
                onClick={() => setFilter('fail')}
              />
              <SummaryCard
                label="Warnings"
                value={findings.summary?.warn ?? 0}
                color="bg-warn"
                active={filter === 'warn'}
                onClick={() => setFilter('warn')}
              />
              <SummaryCard
                label="Skipped"
                value={findings.summary?.skipped ?? 0}
                color="bg-skipped"
                active={filter === 'skipped'}
                onClick={() => setFilter('skipped')}
              />
            </div>

            {/* Metadata */}
            <div className="bg-white rounded-lg shadow-sm p-4 mb-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Target:</span>{' '}
                  <span className="font-medium">{findings.target}</span>
                </div>
                <div>
                  <span className="text-gray-500">Run ID:</span>{' '}
                  <span className="font-mono text-xs">{findings.runId ?? 'N/A'}</span>
                </div>
                <div>
                  <span className="text-gray-500">Timestamp:</span>{' '}
                  <span>{new Date(findings.timestamp).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-gray-500">Version:</span>{' '}
                  <span>{findings.version}</span>
                </div>
              </div>
            </div>

            {/* Checks list */}
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

            {/* Reset button */}
            <div className="mt-6 text-center">
              <button
                onClick={() => setFindings(null)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Load different file
              </button>
            </div>
          </>
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

function SummaryCard({ label, value, color, active, onClick }: SummaryCardProps) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-lg text-white transition-all ${color} ${
        active ? 'ring-2 ring-offset-2 ring-gray-900' : 'opacity-80 hover:opacity-100'
      }`}
    >
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-sm opacity-90">{label}</div>
    </button>
  );
}

export default App;
