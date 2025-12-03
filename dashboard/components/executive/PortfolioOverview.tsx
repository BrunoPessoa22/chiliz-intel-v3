'use client';

interface PortfolioData {
  total_market_cap: number;
  total_volume_24h: number;
  avg_health_score: number;
  tokens_count: number;
  tokens_grade_a: number;
  tokens_grade_b: number;
  tokens_grade_c: number;
  tokens_grade_d: number;
  tokens_grade_f: number;
  top_performer: string | null;
  top_performer_change: number | null;
  worst_performer: string | null;
  worst_performer_change: number | null;
}

export function PortfolioOverview({ data }: { data: PortfolioData | null }) {
  if (!data) return null;

  const formatCurrency = (value: number) => {
    if (value >= 1_000_000_000) return `$${(value / 1_000_000_000).toFixed(2)}B`;
    if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(2)}M`;
    if (value >= 1_000) return `$${(value / 1_000).toFixed(2)}K`;
    return `$${value.toFixed(2)}`;
  };

  const getGradeColor = (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 75) return 'text-lime-400';
    if (score >= 60) return 'text-yellow-400';
    if (score >= 40) return 'text-orange-400';
    return 'text-red-400';
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Total Market Cap */}
      <div className="card">
        <p className="text-gray-400 text-sm">Total Market Cap</p>
        <p className="text-3xl font-bold mt-2">{formatCurrency(data.total_market_cap)}</p>
        <p className="text-xs text-gray-500 mt-1">{data.tokens_count} tokens tracked</p>
      </div>

      {/* 24h Volume */}
      <div className="card">
        <p className="text-gray-400 text-sm">24h Volume</p>
        <p className="text-3xl font-bold mt-2">{formatCurrency(data.total_volume_24h)}</p>
        <p className="text-xs text-gray-500 mt-1">Across all exchanges</p>
      </div>

      {/* Average Health Score */}
      <div className="card">
        <p className="text-gray-400 text-sm">Avg Health Score</p>
        <p className={`text-3xl font-bold mt-2 ${getGradeColor(data.avg_health_score)}`}>
          {data.avg_health_score.toFixed(0)}/100
        </p>
        <div className="flex gap-2 mt-2 text-xs">
          <span className="text-green-400">A:{data.tokens_grade_a}</span>
          <span className="text-lime-400">B:{data.tokens_grade_b}</span>
          <span className="text-yellow-400">C:{data.tokens_grade_c}</span>
          <span className="text-orange-400">D:{data.tokens_grade_d}</span>
          <span className="text-red-400">F:{data.tokens_grade_f}</span>
        </div>
      </div>

      {/* Top & Worst Performers */}
      <div className="card">
        <p className="text-gray-400 text-sm">24h Performance</p>
        <div className="mt-2 space-y-2">
          {data.top_performer && (
            <div className="flex justify-between items-center">
              <span className="text-green-400 font-medium">{data.top_performer}</span>
              <span className="text-green-400">+{data.top_performer_change?.toFixed(2)}%</span>
            </div>
          )}
          {data.worst_performer && (
            <div className="flex justify-between items-center">
              <span className="text-red-400 font-medium">{data.worst_performer}</span>
              <span className="text-red-400">{data.worst_performer_change?.toFixed(2)}%</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
