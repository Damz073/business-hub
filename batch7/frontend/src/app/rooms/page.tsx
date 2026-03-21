"use client";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { InventoryResponse, ManualRateResponse, RoomTypeItem, RoomTypeResponse } from "@/types/hospitality";

const EMPTY_FORM = { code: "", name: "", quantity_total: 1, bed_setup: "", capacity: 2, base_rate: 0, notes: "" };
const EMPTY_RATE = { room_code: "", rate_value: 0, period: "daily", note: "" };

export default function RoomsPage() { return <ProtectedPage>{() => <RoomsContent />}</ProtectedPage>; }

function RoomsContent() {
  const [roomTypes, setRoomTypes] = useState<RoomTypeItem[]>([]);
  const [inventory, setInventory] = useState<InventoryResponse | null>(null);
  const [rates, setRates] = useState<ManualRateResponse | null>(null);
  const [roomForm, setRoomForm] = useState(EMPTY_FORM);
  const [rateForm, setRateForm] = useState(EMPTY_RATE);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    const [roomsPayload, inventoryPayload, ratesPayload] = await Promise.all([
      apiFetch<RoomTypeResponse>("/hospitality/room-types"),
      apiFetch<InventoryResponse>("/hospitality/inventory"),
      apiFetch<ManualRateResponse>("/hospitality/rates"),
    ]);
    setRoomTypes(roomsPayload.items);
    setInventory(inventoryPayload);
    setRates(ratesPayload);
    setRateForm((prev) => ({ ...prev, room_code: prev.room_code || roomsPayload.items[0]?.code || "" }));
  }

  useEffect(() => { load().catch((err) => setError(err.message || "Erro ao carregar quartos.")); }, []);
  const totalUnits = useMemo(() => roomTypes.reduce((sum, item) => sum + Number(item.quantity_total || 0), 0), [roomTypes]);

  async function saveRoomType(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      await apiFetch("/hospitality/room-types", { method: "POST", body: JSON.stringify(roomForm) });
      setRoomForm(EMPTY_FORM); await load(); setSuccess("Tipologia salva com sucesso.");
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar tipologia."); }
    finally { setSaving(false); }
  }

  async function saveRate(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      await apiFetch("/hospitality/rates", { method: "POST", body: JSON.stringify(rateForm) });
      await load(); setSuccess("Tarifa manual aplicada com sucesso.");
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar tarifa."); }
    finally { setSaving(false); }
  }

  function editItem(item: RoomTypeItem) {
    setRoomForm({ code: item.code, name: item.name, quantity_total: Number(item.quantity_total || 1), bed_setup: item.bed_setup || "", capacity: Number(item.capacity || 2), base_rate: Number(item.base_rate || 0), notes: item.notes || "" });
    setSuccess(`Editando ${item.code}. Salve novamente para atualizar.`);
  }

  async function deleteItem(item: RoomTypeItem) {
    if (!window.confirm(`Excluir o tipo de quarto ${item.code}?`)) return;
    setError(""); setSuccess("");
    try {
      await apiFetch(`/hospitality/room-types/${item.id}`, { method: 'DELETE' });
      await load();
      if (roomForm.code === item.code) setRoomForm(EMPTY_FORM);
      setSuccess(`Tipo ${item.code} removido com sucesso.`);
    } catch (err) { setError(err instanceof Error ? err.message : 'Erro ao excluir tipologia.'); }
  }

  return (
    <div className="page-grid">
      <div className="cards-grid">
        <div className="card metric-card"><div className="metric-kicker">Inventário</div><div className="metric-title">Total de unidades</div><div className="metric-value">{new Intl.NumberFormat("pt-BR").format(totalUnits)}</div><div className="metric-subtitle">Somatório das quantidades por tipologia</div></div>
        <div className="card metric-card"><div className="metric-kicker">Operação</div><div className="metric-title">Tipos ativos</div><div className="metric-value">{new Intl.NumberFormat("pt-BR").format(roomTypes.length)}</div><div className="metric-subtitle">Estrutura usada por reservas, cotação e automações</div></div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {success ? <div className="helper-box">{success}</div> : null}

      <div className="split-grid">
        <div className="card fade-up">
          <div className="section-row"><h2 className="section-title">Quartos e tipologias</h2><div className="pill info">Estrutura principal</div></div>
          <p className="inline-note">Cadastre aqui as tipologias da pousada. O bot usa essas informações para cotação rápida, capacidade, valor base e disponibilidade estimada.</p>
          <form onSubmit={saveRoomType} className="form-grid">
            <div className="two-col">
              <label className="label">Código<input className="input" value={roomForm.code} onChange={(e) => setRoomForm({ ...roomForm, code: e.target.value.toUpperCase() })} required /></label>
              <label className="label">Nome<input className="input" value={roomForm.name} onChange={(e) => setRoomForm({ ...roomForm, name: e.target.value })} required /></label>
              <label className="label">Quantidade<input className="input" type="number" value={roomForm.quantity_total} onChange={(e) => setRoomForm({ ...roomForm, quantity_total: Number(e.target.value) })} /></label>
              <label className="label">Capacidade<input className="input" type="number" value={roomForm.capacity} onChange={(e) => setRoomForm({ ...roomForm, capacity: Number(e.target.value) })} /></label>
              <label className="label">Camas<input className="input" value={roomForm.bed_setup} onChange={(e) => setRoomForm({ ...roomForm, bed_setup: e.target.value })} /></label>
              <label className="label">Valor base<input className="input" type="number" value={roomForm.base_rate} onChange={(e) => setRoomForm({ ...roomForm, base_rate: Number(e.target.value) })} /></label>
            </div>
            <label className="label">Observações<textarea className="input" value={roomForm.notes} onChange={(e) => setRoomForm({ ...roomForm, notes: e.target.value })} /></label>
            <button className="button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar tipologia"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <div className="section-row"><h2 className="section-title">Tarifa manual rápida</h2><div className="pill warning">Sem PMS</div></div>
          <p className="inline-note">Use esta área para definir valores diários ou semanais. Também existe suporte a comandos pelo WhatsApp admin.</p>
          <form onSubmit={saveRate} className="form-grid">
            <label className="label">Tipo de quarto
              <select className="input" value={rateForm.room_code} onChange={(e) => setRateForm({ ...rateForm, room_code: e.target.value })}>
                {roomTypes.map((item) => <option key={item.id} value={item.code}>{item.code} • {item.name}</option>)}
              </select>
            </label>
            <div className="two-col">
              <label className="label">Valor<input className="input" type="number" value={rateForm.rate_value} onChange={(e) => setRateForm({ ...rateForm, rate_value: Number(e.target.value) })} /></label>
              <label className="label">Período<select className="input" value={rateForm.period} onChange={(e) => setRateForm({ ...rateForm, period: e.target.value })}><option value="daily">Hoje</option><option value="weekly">Semana</option></select></label>
            </div>
            <label className="label">Observação<input className="input" value={rateForm.note} onChange={(e) => setRateForm({ ...rateForm, note: e.target.value })} /></label>
            <button className="button success" type="submit" disabled={saving}>{saving ? "Aplicando..." : "Aplicar tarifa"}</button>
          </form>
          <div className="helper-box" style={{ marginTop: 16 }}>{rates?.status_text || "As tarifas ativas aparecerão aqui."}</div>
        </div>
      </div>

      <div className="split-grid">
        <div className="card fade-up">
          <h2 className="section-title">Tipologias cadastradas</h2>
          <SimpleTable headers={["Código", "Nome", "Qtd", "Camas", "Capacidade", "Base", "Ações"]} rows={roomTypes.map((item) => [item.code, item.name, String(item.quantity_total || 0), item.bed_setup || "-", String(item.capacity || 0), formatCurrency(item.base_rate || 0), <div key={`room-actions-${item.id}`} style={{ display: 'flex', gap: 8 }}><button className="button ghost" onClick={() => editItem(item)}>Editar</button><button className="button secondary" onClick={() => deleteItem(item)}>Excluir</button></div>])} />
        </div>
        <div className="card fade-up">
          <h2 className="section-title">Disponibilidade estimada</h2>
          <SimpleTable headers={["Quarto", "Livre", "Ocupado", "Capacidade", "Tarifa ativa"]} rows={(inventory?.items || []).map((item) => [item.name, String(item.available_estimate), String(item.occupied_estimate), `${item.capacity} hóspedes`, formatCurrency(item.effective_rate)])} />
        </div>
      </div>
    </div>
  );
}
