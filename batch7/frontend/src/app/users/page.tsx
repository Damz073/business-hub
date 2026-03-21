"use client";

import { FormEvent, useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { RestaurantInfo, RestaurantUserItem, RestaurantUserResponse } from "@/types/management";

const ROLE_OPTIONS = ["admin", "staff", "financeiro", "atendimento"];

export default function UsersPage() {
  return <ProtectedPage>{() => <UsersContent />}</ProtectedPage>;
}

function UsersContent() {
  const [users, setUsers] = useState<RestaurantUserItem[]>([]);
  const [info, setInfo] = useState<RestaurantInfo | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ nome: "", telefone: "", role: "staff" });

  async function load() {
    const [usersData, infoData] = await Promise.all([
      apiFetch<RestaurantUserResponse>("/restaurant-users"),
      apiFetch<RestaurantInfo>("/restaurant-info"),
    ]);
    setUsers(usersData.items || []);
    setInfo(infoData);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message || "Erro ao carregar usuários."));
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true); setError(""); setSuccess("");
    try {
      const result = await apiFetch<RestaurantUserResponse & { ok: boolean }>("/restaurant-users", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setUsers(result.items || []);
      setForm({ nome: "", telefone: "", role: "staff" });
      setSuccess("Usuário adicionado com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao adicionar usuário.");
    } finally {
      setSaving(false);
    }
  }

  async function updateRole(userId: number, role: string) {
    setError(""); setSuccess("");
    try {
      const result = await apiFetch<RestaurantUserResponse & { ok: boolean }>(`/restaurant-users/${userId}`, {
        method: "PUT",
        body: JSON.stringify({ role }),
      });
      setUsers(result.items || []);
      setSuccess("Função atualizada com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao atualizar função.");
    }
  }

  async function removeUser(userId: number) {
    if (!window.confirm("Deseja remover este usuário?")) return;
    setError(""); setSuccess("");
    try {
      const result = await apiFetch<RestaurantUserResponse & { ok: boolean }>(`/restaurant-users/${userId}`, {
        method: "DELETE",
      });
      setUsers(result.items || []);
      setSuccess("Usuário removido com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover usuário.");
    }
  }

  return (
    <div className="page-grid">
      <div className="card hero-panel fade-up">
        <div className="hero-copy">
          <div className="eyebrow">Equipe e permissões</div>
          <h2>Gerencie quem opera a empresa e o papel de cada pessoa.</h2>
          <p>Adicione usuários do WhatsApp da empresa, troque a função e remova acessos direto pelo dashboard.</p>
        </div>
        <div className="stat-strip">
          <div className="pill info">{users.length} usuários</div>
          <div className="pill success">{info?.restaurant_name || "Negócio ativo"}</div>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {success ? <div className="success-box">{success}</div> : null}

      <div className="split-grid users-layout">
        <div className="card fade-up">
          <h2 className="section-title">Adicionar usuário</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="label">Nome
              <input className="input" value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} required />
            </label>
            <label className="label">Telefone
              <input className="input" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: e.target.value })} required />
            </label>
            <label className="label">Função
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
              </select>
            </label>
            <button className="button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Adicionar usuário"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Resumo do negócio</h2>
          <div className="cards-grid compact-cards">
            <div className="card compact-card"><div className="metric-title">Empresa</div><div className="metric-value" style={{fontSize:20}}>{info?.restaurant_name || "-"}</div></div>
            <div className="card compact-card"><div className="metric-title">Plano</div><div className="metric-value" style={{fontSize:20}}>{info?.plano || "-"}</div></div>
            <div className="card compact-card"><div className="metric-title">Status</div><div className="metric-value" style={{fontSize:20}}>{info?.status || "-"}</div></div>
            <div className="card compact-card"><div className="metric-title">Vencimento</div><div className="metric-value" style={{fontSize:20}}>{info?.vencimento || "-"}</div></div>
          </div>
        </div>
      </div>

      <div className="card fade-up">
        <div className="section-row"><h2 className="section-title">Usuários do WhatsApp da empresa</h2><div className="pill info">{users.length} cadastrados</div></div>
        <div className="team-grid">
          {users.map((item) => (
            <div className="team-card" key={item.id}>
              <div className="team-card-head">
                <div>
                  <div className="team-name">{item.nome}</div>
                  <div className="team-phone">{item.telefone}</div>
                </div>
                <span className={`pill ${item.active ? "success" : "warning"}`}>{item.active ? "ativo" : "inativo"}</span>
              </div>
              <div className="team-card-body">
                <label className="label">Função
                  <select className="input" value={item.role} onChange={(e) => updateRole(item.id, e.target.value)}>
                    {ROLE_OPTIONS.map((role) => <option key={role} value={role}>{role}</option>)}
                  </select>
                </label>
                <div className="team-meta">Criado em {formatDateTime(item.created_at)}</div>
              </div>
              <div className="team-card-actions">
                <button className="button secondary" onClick={() => updateRole(item.id, item.role)}>Salvar função</button>
                <button className="button ghost" onClick={() => removeUser(item.id)}>Remover</button>
              </div>
            </div>
          ))}
          {!users.length ? <div className="empty-box">Nenhum usuário cadastrado ainda.</div> : null}
        </div>
      </div>
    </div>
  );
}
