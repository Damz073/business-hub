import { formatCurrency } from "@/lib/format";

type MetricFormat = "currency" | "number";

export function MetricCard({ title, value, subtitle, format = "currency" }: { title: string; value: number; subtitle?: string; format?: MetricFormat; }) {
  const display = format === "number" ? new Intl.NumberFormat("pt-BR").format(Number(value || 0)) : formatCurrency(value);
  return (
    <div className="card metric-card fade-up">
      <div className="metric-kicker">Visão rápida</div>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{display}</div>
      {subtitle ? <div className="metric-subtitle">{subtitle}</div> : null}
    </div>
  );
}
