"use client";

import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { TransactionItem, TransactionListResponse } from "@/types/transaction";

export default function TransactionsPage() {
  return <ProtectedPage>{() => <TransactionsContent />}</ProtectedPage>;
}

function TransactionsContent() {
  const [tipo, setTipo] = useState("");
  const [data, setData] = useState<TransactionListResponse | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState<TransactionItem | null>(null);
  const [form, setForm] = useState({ tipo: "entrada", categoria: "", valor: 0, descricao: "" });

  async function load() {
    const query = tipo ? `/transactions?tipo=${encodeURIComponent(tipo)}` : "/transactions";
    const result = await apiFetch<TransactionListResponse>(query);
    setData(result);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || "Erro ao carregar transações."));
  }, [tipo]);

  function startEdit(item: TransactionItem) {
    setEditing(item);
    setForm({ tipo: item.tipo, categoria: item.categoria, valor: item.valor, descricao: item.descricao || "" });
    setSuccess("");
    setError("");
  }

  async function saveEdit() {
    if (!editing) return;
    try {
      const result = await apiFetch<TransactionListResponse & { ok: boolean }>(`/transactions/${editing.id}`, {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setData({ count: result.items.length, items: result.items });
      setEditing(null);
      setSuccess("Transação atualizada com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar transação.");
    }
  }

  async function removeItem(item: TransactionItem) {
    if (!window.confirm(`Remover a transação ${item.descricao || item.categoria}?`)) return;
    try {
      const result = await apiFetch<TransactionListResponse & { ok: boolean }>(`/transactions/${item.id}`, { method: "DELETE" });
      setData({ count: result.items.length, items: result.items });
      setSuccess("Transação removida com sucesso.");
      if (editing?.id === item.id) setEditing(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover transação.");
    }
  }

  return (
    <div className="page-grid">
      <div className="card fade-up">
        <div className="section-row"><h2 className="section-title">Financeiro</h2><div className="pill info">edição habilitada</div></div>
        <div className="filters">
          <label className="label">
            Tipo
            <select className="input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
              <option value="">Todos</option>
              <option value="entrada">Entrada</option>
              <option value="despesa">Despesa</option>
            </select>
          </label>
        </div>
        {error ? <div className="error-box">{error}</div> : null}
        {success ? <div className="success-box">{success}</div> : null}
        {editing ? (
          <div className="card compact-card" style={{ marginBottom: 16 }}>
            <h3 className="section-title" style={{ marginBottom: 12 }}>Editar transação #{editing.id}</h3>
            <div className="two-col">
              <label className="label">Tipo<select className="input" value={form.tipo} onChange={(e) => setForm({ ...form, tipo: e.target.value })}><option value="entrada">Entrada</option><option value="despesa">Despesa</option></select></label>
              <label className="label">Categoria<input className="input" value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })} /></label>
              <label className="label">Valor<input className="input" type="number" value={form.valor} onChange={(e) => setForm({ ...form, valor: Number(e.target.value) })} /></label>
              <label className="label">Descrição<input className="input" value={form.descricao} onChange={(e) => setForm({ ...form, descricao: e.target.value })} /></label>
            </div>
            <div className="team-card-actions">
              <button className="button" onClick={saveEdit}>Salvar alterações</button>
              <button className="button ghost" onClick={() => setEditing(null)}>Cancelar</button>
            </div>
          </div>
        ) : null}
        <SimpleTable
          headers={["Data", "Descrição", "Categoria", "Tipo", "Valor", "Ações"]}
          rows={(data?.items || []).map((item) => [
            formatDateTime(item.criado_em),
            item.descricao,
            item.categoria,
            item.tipo,
            formatCurrency(item.valor),
            <div key={`tx-actions-${item.id}`} style={{ display: 'flex', gap: 8 }}>
              <button className="button secondary" onClick={() => startEdit(item)}>Editar</button>
              <button className="button ghost" onClick={() => removeItem(item)}>Excluir</button>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}
