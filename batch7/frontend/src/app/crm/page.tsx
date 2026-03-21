"use client";
import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { CustomerItem } from "@/types/core";

export default function CrmPage() { return <ProtectedPage>{() => <CrmContent />}</ProtectedPage>; }

function CrmContent() {
  const [items, setItems] = useState<CustomerItem[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { apiFetch<{items: CustomerItem[]}>('/core/customers').then((res) => setItems(res.items || [])).catch((err) => setError(err.message || 'Erro ao carregar CRM.')); }, []);
  return (
    <div className="page-grid">
      {error ? <div className="error-box">{error}</div> : null}
      <div className="card fade-up">
        <div className="section-row"><h2 className="section-title">CRM universal</h2><div className="pill info">Base compartilhada entre módulos</div></div>
        <p className="inline-note">Cada cliente atendido pelo WhatsApp entra automaticamente nesta base. É a fundação para campanhas, histórico e operação multi-segmento.</p>
        <div className="crm-list">
          {items.map((item) => (
            <div key={item.id} className="crm-card">
              <div>
                <div className="crm-name">{item.name || item.phone}</div>
                <div className="crm-phone">{item.phone}</div>
              </div>
              <div className="crm-meta">
                <span className="pill info">{item.customer_type}</span>
                <span className="pill success">{item.lifecycle_stage}</span>
              </div>
              <div className="inline-note">Última interação: {formatDateTime(item.last_message_at || '') || '-'}</div>
              <div className="inline-note">Receita acumulada: {formatCurrency(item.total_revenue || 0)}</div>
            </div>
          ))}
          {!items.length ? <div className="page-state">Ainda não há clientes registrados no CRM.</div> : null}
        </div>
      </div>
    </div>
  );
}
