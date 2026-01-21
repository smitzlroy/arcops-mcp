import { type Check, getStatusColor, getStatusBgColor, getSeverityColor } from '../lib/schema';

interface CheckCardProps {
  check: Check;
  expanded?: boolean;
  onToggle?: () => void;
}

export function CheckCard({ check, expanded = false, onToggle }: CheckCardProps) {
  const statusColor = getStatusColor(check.status);
  const statusBgColor = getStatusBgColor(check.status);
  const severityColor = getSeverityColor(check.severity);

  return (
    <div
      className={`bg-white rounded-lg shadow-sm border-l-4 ${statusBgColor.replace('bg-', 'border-')} overflow-hidden`}
    >
      <div
        className="p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <StatusIcon status={check.status} />
              <h3 className="font-medium text-gray-900">{check.title}</h3>
            </div>
            <p className="text-sm text-gray-500 font-mono">{check.id}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2 py-1 rounded text-xs font-medium ${severityColor}`}>
              {check.severity.toUpperCase()}
            </span>
            <span className={`px-2 py-1 rounded text-xs font-medium ${statusColor} bg-opacity-10`}>
              {check.status.toUpperCase()}
            </span>
          </div>
        </div>
      </div>

      {expanded && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3">
          {check.description && (
            <p className="text-sm text-gray-600 mb-3">{check.description}</p>
          )}

          {check.hint && (
            <div className="bg-amber-50 border border-amber-200 rounded p-3 mb-3">
              <p className="text-sm text-amber-800">
                <strong>💡 Hint:</strong> {check.hint}
              </p>
            </div>
          )}

          {check.evidence && Object.keys(check.evidence).length > 0 && (
            <div className="mb-3">
              <h4 className="text-sm font-medium text-gray-700 mb-2">Evidence</h4>
              <pre className="bg-gray-50 rounded p-3 text-xs overflow-x-auto">
                {JSON.stringify(check.evidence, null, 2)}
              </pre>
            </div>
          )}

          {check.sources && check.sources.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-2">Sources</h4>
              <ul className="space-y-1">
                {check.sources.map((source, i) => (
                  <li key={i} className="text-sm">
                    <span className="inline-block px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs mr-2">
                      {source.type}
                    </span>
                    {source.url ? (
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {source.label}
                      </a>
                    ) : (
                      <span className="text-gray-600">{source.label}</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {check.duration_ms !== undefined && (
            <p className="text-xs text-gray-400 mt-3">
              Duration: {check.duration_ms}ms
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function StatusIcon({ status }: { status: Check['status'] }) {
  switch (status) {
    case 'pass':
      return <span className="text-pass text-lg">✓</span>;
    case 'fail':
      return <span className="text-fail text-lg">✗</span>;
    case 'warn':
      return <span className="text-warn text-lg">⚠</span>;
    case 'skipped':
      return <span className="text-skipped text-lg">○</span>;
  }
}

export default CheckCard;
