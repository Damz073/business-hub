"use client";
import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { MetricCard } from "@/components/MetricCard";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { DashboardSummary } from "@/types/dashboard";
import { HospitalitySummary } from "@/types/hospitality";
import { AuthUser } from "@/types/auth";
import { CoreOverview } from "@/types/core";

export default function DashboardPage() { return <ProtectedPage>{(user) => <DashboardContent user={user} />}</ProtectedPage>; }

function DashboardContent({ user }: { user: AuthUser }) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [hospitality, setHospitality] = useState<HospitalitySummary | null>(null);
  const [error, setError] = useState("");
  const [coreOverview, setCoreOverview] = useState<CoreOverview | null>(null);
  useEffect(() => {
    apiFetch<DashboardSummary>("/dashboard/summary").then(setData).catch((err) => setError(err.message || "Erro ao carregar dashboard."));
    apiFetch<CoreOverview>("/core/overview").then(setCoreOverview).catch(() => null);
    if (user.business_type === "hospitality") apiFetch<HospitalitySummary>("/hospitality/summary").then(setHospitality).catch(() => null);
  }, [user.business_type]);
  if (error) return <div className="error-box">{error}</div>;
  if (!data) return <div className="page-state">Carregando resumo...</div>;
  return (
    <div className="page-grid">
      <div className="card hero-panel fade-up">
        <div className="hero-copy">
          <div className="eyebrow">Visão executiva</div>
          <h2>Operação, reservas e financeiro no mesmo lugar.</h2>
          <p>Este painel foi redesenhado para ficar mais profissional e mais rápido no uso diário, com foco em reservas, atendimento híbrido, financeiro e configurações operacionais.</p>
        </div>
        <div className="stat-strip">
          <div className="pill info">Modo: {user.business_type}</div>
          <div className="pill success">Conta ativa</div>
        </div>
      </div>

      <div className="cards-grid">
        <MetricCard title="Saldo atual" value={data.saldo_atual} subtitle={`${data.quantidade_transacoes} transações`} />
        <MetricCard title="Entradas" value={data.total_entradas} subtitle="Histórico total" />
        <MetricCard title="Despesas" value={data.total_despesas} subtitle="Histórico total" />
        <MetricCard title="Saldo do mês" value={data.mes_atual.saldo} subtitle={`${data.mes_atual.quantidade_transacoes} transações no mês`} />
      </div>

      {coreOverview ? (
        <div className="cards-grid">
          <MetricCard title="Clientes no CRM" value={coreOverview.metrics.customers} subtitle="Base universal" format="number" />
          <MetricCard title="Conversas" value={coreOverview.metrics.conversations} subtitle="Inbox compartilhada" format="number" />
          <MetricCard title="Time" value={coreOverview.metrics.team_members} subtitle="Usuários web ativos" format="number" />
          <MetricCard title="Modelo SaaS" value={coreOverview.metrics.reservations} subtitle={`${coreOverview.saas_mode} • ${coreOverview.growth_stage}`} format="number" />
        </div>
      ) : null}

      {user.business_type === "hospitality" && hospitality ? (
        <>
          <div className="cards-grid">
            <MetricCard title="Conversas" value={hospitality.conversas.total} subtitle={`${hospitality.conversas.em_humano} com humano`} format="number" />
            <MetricCard title="Leads de reserva" value={hospitality.reservas.leads_abertos} subtitle={`${hospitality.reservas.pagamentos_pendentes} pagamentos pendentes`} format="number" />
            <MetricCard title="Receita confirmada" value={hospitality.reservas.receita_confirmada} subtitle="Reservas confirmadas" />
            <MetricCard title="Inventário" value={hospitality.inventario?.unidades || 0} subtitle={`${hospitality.inventario?.tipos || 0} tipologias`} format="number" />
          </div>

          <div className="split-grid">
            <div className="card fade-up">
              <div className="section-row"><h2 className="section-title">Inbox recente</h2><div className="pill info">Últimas conversas</div></div>
              <SimpleTable headers={["Última interação", "Telefone", "Status", "Mensagem"]} rows={hospitality.inbox_recente.map((item) => [formatDateTime(item.last_message_at), item.customer_phone, <span className="pill info" key={`${item.id}-status`}>{item.status}</span>, item.last_customer_message || "-"])} />
            </div>
            <div className="card fade-up">
              <div className="section-row"><h2 className="section-title">Inventário operacional</h2><div className="pill success">Disponibilidade estimada</div></div>
              <SimpleTable headers={["Quarto", "Livre", "Ocupado", "Capacidade", "Tarifa"]} rows={(hospitality.inventory_snapshot || []).map((item) => [item.name, String(item.available_estimate), String(item.occupied_estimate), `${item.capacity} hóspedes`, formatCurrency(item.effective_rate)])} />
            </div>
          </div>

          <div className="split-grid">
            <div className="card fade-up">
              <div className="section-row"><h2 className="section-title">Reservas recentes</h2><div className="pill warning">Fluxo operacional</div></div>
              <SimpleTable headers={["Hóspede", "Período", "Status", "Pagamento", "Valor"]} rows={hospitality.reservas_recentes.map((item) => [item.guest_name || item.guest_phone, `${item.checkin_date || "-"} → ${item.checkout_date || "-"}`, item.status, item.payment_status, formatCurrency(item.quoted_amount || 0)])} />
            </div>
            <div className="card fade-up">
              <div className="section-row"><h2 className="section-title">Tarifas manuais</h2><div className="pill info">Manual rates</div></div>
              <SimpleTable headers={["Código", "Tarifa", "Válida até"]} rows={(hospitality.manual_rates || []).map((item) => [item.room_code, formatCurrency(item.rate_value), item.valid_until])} />
            </div>
          </div>
        </>
      ) : null}

      <div className="card fade-up">
        <h2 className="section-title">Últimas transações</h2>
        <SimpleTable headers={["Data", "Descrição", "Categoria", "Tipo", "Valor"]} rows={data.ultimas_transacoes.map((item) => [formatDateTime(item.criado_em), item.descricao, item.categoria, item.tipo, formatCurrency(item.valor)])} />
      </div>
    </div>
  );
}
