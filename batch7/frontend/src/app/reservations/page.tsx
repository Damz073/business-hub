"use client";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { ReservationItem, ReservationResponse, RoomTypeResponse } from "@/types/hospitality";

export default function ReservationsPage() { return <ProtectedPage>{() => <ReservationsContent />}</ProtectedPage>; }

type ReservationForm = {
  guest_name: string;
  guest_phone: string;
  checkin_date: string;
  checkout_date: string;
  guest_count: number;
  unit_category: string;
  quoted_amount: number;
  notes: string;
  notes_internal: string;
  source: string;
  main_guest_name: string;
  main_guest_phone: string;
  guest_document: string;
  guest_email: string;
  guest_city: string;
  car_plate: string;
  estimated_arrival: string;
  guests: Array<{ name: string }>;
};

const emptyForm: ReservationForm = {
  guest_name: "", guest_phone: "", checkin_date: "", checkout_date: "", guest_count: 2, unit_category: "", quoted_amount: 0,
  notes: "", notes_internal: "", source: "balcao", main_guest_name: "", main_guest_phone: "", guest_document: "", guest_email: "",
  guest_city: "", car_plate: "", estimated_arrival: "", guests: [{ name: "" }],
};

function ReservationsContent() {
  const [data, setData] = useState<ReservationResponse | null>(null);
  const [rooms, setRooms] = useState<RoomTypeResponse | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState<ReservationForm>(emptyForm);

  async function load() {
    try {
      const [r, m] = await Promise.all([apiFetch<ReservationResponse>("/hospitality/reservations"), apiFetch<RoomTypeResponse>("/hospitality/room-types")]);
      setData(r); setRooms(m);
      if (m.items[0] && !form.unit_category) setForm((c) => ({ ...c, unit_category: m.items[0].code }));
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao carregar reservas."); }
  }

  useEffect(() => { load(); }, []);

  const summary = useMemo(() => {
    const items = data?.items || [];
    return {
      total: items.length,
      awaiting: items.filter((item) => item.status === 'aguardando_pagamento').length,
      confirmed: items.filter((item) => item.status === 'confirmada').length,
      revenue: items.filter((item) => item.payment_status === 'confirmado').reduce((sum, item) => sum + Number(item.total_value || item.quoted_amount || 0), 0),
    };
  }, [data]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      await apiFetch("/hospitality/reservations", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          source: form.source,
          main_guest_name: form.main_guest_name || form.guest_name,
          main_guest_phone: form.main_guest_phone || form.guest_phone,
          guests: form.guests.filter((guest) => guest.name.trim()).map((guest) => ({ name: guest.name.trim() })),
          total_value: form.quoted_amount,
        }),
      });
      setForm({ ...emptyForm, unit_category: rooms?.items[0]?.code || "" });
      setSuccess("Reserva profissional criada com sucesso.");
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar reserva."); }
    finally { setSaving(false); }
  }

  async function confirmPayment(id: number) {
    setConfirmingId(id); setError(""); setSuccess("");
    try {
      const result = await apiFetch<{customer_notify?: {status_code?: number}; item?: ReservationItem}>(`/hospitality/reservations/${id}/confirm-payment`, { method: "POST" });
      const notifyStatus = result?.customer_notify?.status_code;
      const guestLabel = result?.item?.main_guest_name || result?.item?.guest_name || result?.item?.guest_phone || "cliente";
      setSuccess(notifyStatus && notifyStatus < 400 ? `Pagamento confirmado e ${guestLabel} notificado no WhatsApp.` : `Pagamento confirmado. Revise a entrega da mensagem para ${guestLabel} no WhatsApp.`);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao confirmar pagamento."); }
    finally { setConfirmingId(null); }
  }

  return (
    <div className="page-grid reservations-premium-page">
      <div className="card hero-panel fade-up premium-glow">
        <div className="hero-copy">
          <div className="eyebrow">Fase 18 • reserva profissional</div>
          <h2>Central de reservas com padrão PMS e ficha completa do hóspede.</h2>
          <p>Agora sua operação já nasce preparada para mapa de reservas, múltiplos hóspedes, status profissionais e gestão mais madura de balcão, telefone, WhatsApp e integrações futuras.</p>
        </div>
        <div className="stat-strip wrap-right">
          <Link className="button" href="/reservations/map">Abrir mapa de reservas</Link>
          <div className="pill info">Código automático</div>
          <div className="pill warning">Modo premium</div>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}
      {success ? <div className="success-box">{success}</div> : null}

      <div className="premium-summary-grid fade-up">
        <div className="card"><div className="metric-kicker">Reservas</div><div className="metric-value">{summary.total}</div><div className="metric-title">Total cadastrado</div></div>
        <div className="card"><div className="metric-kicker">Aguardando</div><div className="metric-value">{summary.awaiting}</div><div className="metric-title">Pagamento ou confirmação</div></div>
        <div className="card"><div className="metric-kicker">Confirmadas</div><div className="metric-value">{summary.confirmed}</div><div className="metric-title">Já prontas para hospedagem</div></div>
        <div className="card"><div className="metric-kicker">Receita</div><div className="metric-value">{formatCurrency(summary.revenue)}</div><div className="metric-title">Entrada confirmada</div></div>
      </div>

      <div className="split-grid split-grid-strong">
        <div className="card fade-up">
          <div className="section-row"><h2 className="section-title">Nova reserva profissional</h2><div className="pill info">Ficha do hóspede inclusa</div></div>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="two-col">
              <label className="label">Nome principal<input className="input" value={form.guest_name} onChange={(e) => setForm({ ...form, guest_name: e.target.value, main_guest_name: e.target.value })} required /></label>
              <label className="label">Telefone principal<input className="input" value={form.guest_phone} onChange={(e) => setForm({ ...form, guest_phone: e.target.value, main_guest_phone: e.target.value })} required /></label>
              <label className="label">Check-in<input className="input" type="date" value={form.checkin_date} onChange={(e) => setForm({ ...form, checkin_date: e.target.value })} /></label>
              <label className="label">Check-out<input className="input" type="date" value={form.checkout_date} onChange={(e) => setForm({ ...form, checkout_date: e.target.value })} /></label>
              <label className="label">Hóspedes<input className="input" type="number" value={form.guest_count} onChange={(e) => setForm({ ...form, guest_count: Number(e.target.value) })} /></label>
              <label className="label">Quarto / tipologia<select className="input" value={form.unit_category} onChange={(e) => setForm({ ...form, unit_category: e.target.value })}>{rooms?.items.map((room) => <option key={room.id} value={room.code}>{room.code} • {room.name}</option>)}</select></label>
              <label className="label">Origem<select className="input" value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}><option value="whatsapp">WhatsApp</option><option value="balcao">Balcão</option><option value="telefone">Telefone</option><option value="site">Site</option></select></label>
              <label className="label">Valor total<input className="input" type="number" value={form.quoted_amount} onChange={(e) => setForm({ ...form, quoted_amount: Number(e.target.value) })} /></label>
              <label className="label">CPF<input className="input" value={form.guest_document} onChange={(e) => setForm({ ...form, guest_document: e.target.value })} /></label>
              <label className="label">E-mail<input className="input" value={form.guest_email} onChange={(e) => setForm({ ...form, guest_email: e.target.value })} /></label>
              <label className="label">Cidade<input className="input" value={form.guest_city} onChange={(e) => setForm({ ...form, guest_city: e.target.value })} /></label>
              <label className="label">Placa do carro<input className="input" value={form.car_plate} onChange={(e) => setForm({ ...form, car_plate: e.target.value })} /></label>
              <label className="label">Previsão de chegada<input className="input" placeholder="Ex: 18:30" value={form.estimated_arrival} onChange={(e) => setForm({ ...form, estimated_arrival: e.target.value })} /></label>
              <label className="label">Acompanhante<input className="input" value={form.guests[0]?.name || ""} onChange={(e) => setForm({ ...form, guests: [{ name: e.target.value }] })} placeholder="Nome do acompanhante" /></label>
            </div>
            <label className="label">Observações da reserva<textarea className="input" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
            <label className="label">Observações internas<textarea className="input" value={form.notes_internal} onChange={(e) => setForm({ ...form, notes_internal: e.target.value })} /></label>
            <button className="button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar reserva profissional"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Estrutura PMS entregue</h2>
          <div className="helper-stack">
            <div className="helper-box"><strong>Status profissionais</strong><br />lead, aguardando_pagamento, confirmada, checkin, checkout, cancelada e bloqueada.</div>
            <div className="helper-box"><strong>Origem comercial</strong><br />WhatsApp, balcão, telefone e site, já preparada para Omnibees ou outro integrador.</div>
            <div className="helper-box"><strong>Ficha do hóspede</strong><br />CPF, e-mail, cidade, placa, previsão de chegada e acompanhantes.</div>
            <div className="helper-box"><strong>Operação visual</strong><br />Use o mapa PMS para enxergar reservas por quarto e por período.</div>
          </div>
        </div>
      </div>

      <div className="card fade-up">
        <div className="section-row"><h2 className="section-title">Reservas registradas</h2><div className="pill info">{data?.count || 0} reservas</div></div>
        <SimpleTable headers={["Código", "Atualizado", "Hóspede", "Período", "Quarto", "Origem", "Status", "Pagamento", "Valor", "Ações"]} rows={(data?.items || []).map((item) => [
          item.reservation_code || `RES-${item.id}`,
          formatDateTime(item.updated_at),
          <div key={`guest-${item.id}`}><strong>{item.main_guest_name || item.guest_name || item.guest_phone}</strong><div className="table-subtext">{item.guest_summary || item.guest_phone}</div></div>,
          `${item.checkin_date || "-"} → ${item.checkout_date || "-"}`,
          item.unit_category || "-",
          item.source || "-",
          <span key={`${item.id}-s`} className={`pill ${item.status === 'confirmada' ? 'success' : item.status === 'cancelada' ? 'danger' : 'warning'}`}>{item.status}</span>,
          <span key={`${item.id}-p`} className={`pill ${item.payment_status === 'confirmado' ? 'success' : 'warning'}`}>{item.payment_status}</span>,
          formatCurrency(item.total_value || item.quoted_amount || 0),
          item.payment_status === 'confirmado' ? <Link key={`${item.id}-view`} className="button ghost table-action-link" href="/reservations/map">Ver no mapa</Link> : <button key={`${item.id}-btn`} className="button success" disabled={confirmingId === item.id} onClick={() => confirmPayment(item.id)}>{confirmingId === item.id ? "Confirmando..." : "Confirmar"}</button>
        ])} />
      </div>
    </div>
  );
}
