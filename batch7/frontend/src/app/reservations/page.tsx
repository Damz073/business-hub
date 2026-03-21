"use client";
import { FormEvent, useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { OccupancyMapResponse, ReservationResponse, RoomTypeResponse } from "@/types/hospitality";

export default function ReservationsPage() { return <ProtectedPage>{() => <ReservationsContent />}</ProtectedPage>; }

function ReservationsContent() {
  const [data, setData] = useState<ReservationResponse | null>(null);
  const [rooms, setRooms] = useState<RoomTypeResponse | null>(null);
  const [occupancy, setOccupancy] = useState<OccupancyMapResponse | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState({ guest_name: "", guest_phone: "", checkin_date: "", checkout_date: "", guest_count: 2, unit_category: "", quoted_amount: 0, notes: "", source: "panel" });

  async function load() {
    try {
      const [r, m, o] = await Promise.all([apiFetch<ReservationResponse>("/hospitality/reservations"), apiFetch<RoomTypeResponse>("/hospitality/room-types"), apiFetch<OccupancyMapResponse>("/hospitality/occupancy-map")]);
      setData(r); setRooms(m); setOccupancy(o);
      if (m.items[0] && !form.unit_category) setForm((c) => ({ ...c, unit_category: m.items[0].code }));
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao carregar reservas."); }
  }

  useEffect(() => { load(); }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      await apiFetch("/hospitality/reservations", { method: "POST", body: JSON.stringify(form) });
      setForm({ guest_name: "", guest_phone: "", checkin_date: "", checkout_date: "", guest_count: 2, unit_category: rooms?.items[0]?.code || "", quoted_amount: 0, notes: "", source: "panel" });
      setSuccess("Reserva criada com sucesso.");
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar reserva."); }
    finally { setSaving(false); }
  }

  async function confirmPayment(id: number) {
    setConfirmingId(id); setError(""); setSuccess("");
    try { const result = await apiFetch<{customer_notify?: {status_code?: number}; item?: {guest_name?: string; guest_phone?: string}}>(`/hospitality/reservations/${id}/confirm-payment`, { method: "POST" });
      const notifyStatus = result?.customer_notify?.status_code;
      const guestLabel = result?.item?.guest_name || result?.item?.guest_phone || "cliente";
      setSuccess(notifyStatus && notifyStatus < 400 ? `Pagamento confirmado e ${guestLabel} notificado no WhatsApp.` : `Pagamento confirmado. Revise a entrega da mensagem para ${guestLabel} no WhatsApp.`);
      await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Erro ao confirmar pagamento."); }
    finally { setConfirmingId(null); }
  }

  return (
    <div className="page-grid">
      <div className="card hero-panel fade-up">
        <div className="hero-copy">
          <div className="eyebrow">Central de reservas</div>
          <h2>Operação de reservas, pagamentos e origem da ocupação.</h2>
          <p>Use esta área para reservas do painel, do WhatsApp, do balcão e, futuramente, do PMS. Quando o pagamento for confirmado, a receita entra no financeiro automaticamente.</p>
        </div>
        <div className="stat-strip">
          <div className="pill info">Origem unificada</div>
          <div className="pill warning">Sincronização PMS pronta</div>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      {success ? <div className="success-box">{success}</div> : null}

      <div className="split-grid">
        <div className="card fade-up">
          <h2 className="section-title">Nova reserva</h2>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="two-col">
              <label className="label">Hóspede<input className="input" value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value })} required /></label>
              <label className="label">Telefone<input className="input" value={form.guest_phone} onChange={(e) => setForm({ ...form, guest_phone: e.target.value })} required /></label>
              <label className="label">Check-in<input className="input" type="date" value={form.checkin_date} onChange={(e) => setForm({ ...form, checkin_date: e.target.value })} /></label>
              <label className="label">Check-out<input className="input" type="date" value={form.checkout_date} onChange={(e) => setForm({ ...form, checkout_date: e.target.value })} /></label>
              <label className="label">Hóspedes<input className="input" type="number" value={form.guest_count} onChange={(e) => setForm({ ...form, guest_count: Number(e.target.value) })} /></label>
              <label className="label">Tipo de quarto<select className="input" value={form.unit_category} onChange={(e) => setForm({ ...form, unit_category: e.target.value })}>{rooms?.items.map((room) => <option key={room.id} value={room.code}>{room.code} • {room.name}</option>)}</select></label>
              <label className="label">Valor cotado<input className="input" type="number" value={form.quoted_amount} onChange={(e) => setForm({ ...form, quoted_amount: Number(e.target.value) })} /></label>
              <label className="label">Origem<select className="input" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}><option value="panel">Painel</option><option value="admin_manual">Admin manual</option><option value="whatsapp">WhatsApp</option><option value="pms_voa">PMS VOA</option></select></label>
            </div>
            <label className="label">Observações<textarea className="input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
            <button className="button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar reserva"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Fluxo do admin no WhatsApp</h2>
          <div className="helper-box">
            <strong>Reserva manual via WhatsApp:</strong><br />
            /reserva balcão Nome; 557399999999; CASAL; 2026-03-20; 2026-03-22; 560; observação
          </div>
          <div className="helper-box">
            <strong>Comandos úteis:</strong><br />
            /assumir 5573...<br />
            /liberar 5573...<br />
            /reservas hoje<br />
            /tarifas semana CASAL 320, FAMILIA 420
          </div>
        </div>
      </div>

      <div className="card fade-up">
        <div className="section-row">
          <h2 className="section-title">Mapa de ocupação</h2>
          <div className="pill info">{occupancy?.count || 0} tipologias</div>
        </div>
        <div className="occupancy-grid">
          {(occupancy?.items || []).map((item) => (
            <div key={item.code} className={`occupancy-card occupancy-${item.occupancy_status}`}>
              <div className="occupancy-head">
                <div>
                  <div className="eyebrow">{item.code}</div>
                  <h3>{item.name}</h3>
                </div>
                <div className={`pill ${item.occupancy_status === 'alta' ? 'warning' : item.occupancy_status === 'media' ? 'info' : 'success'}`}>{item.occupancy_pct}% ocupado</div>
              </div>
              <div className="occupancy-bar"><span style={{ width: `${Math.min(100, item.occupancy_pct)}%` }} /></div>
              <div className="occupancy-meta">
                <strong>{item.occupied_estimate}</strong> confirmados • <strong>{item.pending_estimate}</strong> pendentes • <strong>{item.blocked_estimate}</strong> bloqueados • <strong>{item.available_estimate}</strong> livres • total {item.total}
              </div>
              <div className="occupancy-note">Capacidade {item.capacity} • {item.bed_setup || 'Configuração não informada'} • tarifa base {formatCurrency(item.effective_rate || 0)}</div>
            </div>
          ))}
        </div>
      </div>


      <div className="card fade-up">
        <div className="section-row"><h2 className="section-title">Reservas registradas</h2><div className="pill info">{data?.count || 0} reservas</div></div>
        <SimpleTable headers={["Atualizado", "Hóspede", "Período", "Quarto", "Origem", "Status", "Pagamento", "Valor", "Ações"]} rows={(data?.items || []).map((item) => [formatDateTime(item.updated_at), item.guest_name || item.guest_phone, `${item.checkin_date || "-"} → ${item.checkout_date || "-"}`, item.unit_category || "-", item.source || "-", <span key={`${item.id}-s`} className="pill info">{item.status}</span>, <span key={`${item.id}-p`} className={`pill ${item.payment_status === 'confirmado' ? 'success' : 'warning'}`}>{item.payment_status}</span>, formatCurrency(item.quoted_amount || 0), item.payment_status === 'confirmado' ? <span key={`${item.id}-ok`} className="pill success">Confirmado</span> : <button key={`${item.id}-btn`} className="button success" disabled={confirmingId === item.id} onClick={() => confirmPayment(item.id)}>{confirmingId === item.id ? "Confirmando..." : "Confirmar"}</button>])} />
      </div>
    </div>
  );
}
