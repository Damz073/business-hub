"use client";

import { useEffect, useMemo, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import type { ReservationCalendarItem, ReservationsCalendarResponse } from "@/types/hospitality";

function addDays(date: Date, amount: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function toIsoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function formatDayLabel(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return {
    weekday: date.toLocaleDateString("pt-BR", { weekday: "short" }),
    day: date.toLocaleDateString("pt-BR", { day: "2-digit" }),
  };
}

function diffDays(start?: string | null, end?: string | null) {
  if (!start || !end) return 1;
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  const value = Math.round((b.getTime() - a.getTime()) / 86400000);
  return Math.max(1, value || 1);
}

const statusToneMap: Record<string, string> = {
  confirmada: "is-confirmed",
  confirmed: "is-confirmed",
  checkin: "is-confirmed",
  checkout: "is-confirmed",
  aguardando_pagamento: "is-pending",
  pending_payment: "is-pending",
  lead: "is-pending",
  cancelada: "is-problem",
  problem: "is-problem",
  bloqueada: "is-blocked",
  blocked: "is-blocked",
};

export default function ReservationsMapPage() {
  return <ProtectedPage>{() => <ReservationsMapContent />}</ProtectedPage>;
}

function ReservationsMapContent() {
  const [data, setData] = useState<ReservationsCalendarResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<ReservationCalendarItem | null>(null);
  const [range, setRange] = useState(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), 1);
    const end = addDays(start, 44);
    return { start_date: toIsoDate(start), end_date: toIsoDate(end) };
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const payload = await apiFetch<ReservationsCalendarResponse>(
        `/hospitality/reservations/calendar?start_date=${range.start_date}&end_date=${range.end_date}`,
      );
      setData(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar mapa de reservas.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [range.start_date, range.end_date]);

  const days = useMemo(() => {
    const list: string[] = [];
    let cursor = new Date(`${(data?.start_date || range.start_date)}T00:00:00`);
    const end = new Date(`${(data?.end_date || range.end_date)}T00:00:00`);
    while (cursor <= end) {
      list.push(toIsoDate(cursor));
      cursor = addDays(cursor, 1);
    }
    return list;
  }, [data?.start_date, data?.end_date, range.start_date, range.end_date]);

  const blocks = useMemo(() => {
    const currentStart = data?.start_date || range.start_date;
    const currentEnd = data?.end_date || range.end_date;
    return (data?.items || []).map((item) => {
      const startIndex = Math.max(0, days.findIndex((day) => day === (item.checkin || currentStart)));
      const tone = statusToneMap[item.status] || "is-pending";
      return {
        ...item,
        tone,
        startIndex,
        span: Math.min(diffDays(item.checkin || currentStart, item.checkout || currentEnd), days.length || 1),
      };
    });
  }, [data?.items, data?.start_date, data?.end_date, range.start_date, range.end_date, days]);

  return (
    <div className="page-grid reservations-map-page">
      <div className="card hero-panel fade-up premium-glow">
        <div className="hero-copy">
          <div className="eyebrow">Fase 18 • mapa de reservas</div>
          <h2>Operação visual no padrão PMS, com leitura rápida de ocupação e status.</h2>
          <p>Visualize a estadia em blocos contínuos por tipologia, acompanhe o pagamento e abra o detalhe completo da reserva sem sair do calendário.</p>
        </div>
        <div className="stat-strip wrap-right">
          <div className="pill success">Confirmado</div>
          <div className="pill warning">Pendente</div>
          <div className="pill">Bloqueio</div>
        </div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="card fade-up reservations-map-toolbar">
        <div className="toolbar-group">
          <label className="label compact">
            Início
            <input className="input" type="date" value={range.start_date} onChange={(e) => setRange((current) => ({ ...current, start_date: e.target.value }))} />
          </label>
          <label className="label compact">
            Fim
            <input className="input" type="date" value={range.end_date} onChange={(e) => setRange((current) => ({ ...current, end_date: e.target.value }))} />
          </label>
          <button className="button secondary" type="button" onClick={load} disabled={loading}>{loading ? "Atualizando..." : "Atualizar mapa"}</button>
        </div>
        <div className="toolbar-summary">
          <div><strong>{data?.count || 0}</strong><span>reservas no período</span></div>
          <div><strong>{days.length}</strong><span>dias visíveis</span></div>
        </div>
      </div>

      <div className="card fade-up reservations-map-board">
        <div className="map-scroll">
          <div className="map-board" style={{ gridTemplateColumns: `220px repeat(${days.length || 1}, minmax(64px, 1fr))` }}>
            <div className="map-corner">Quartos / tipologias</div>
            {days.map((day) => {
              const label = formatDayLabel(day);
              return (
                <div key={day} className="map-day-header">
                  <span>{label.weekday}</span>
                  <strong>{label.day}</strong>
                </div>
              );
            })}

            {(data?.rooms || []).map((room) => {
              const roomBlocks = blocks.filter((item) => item.room_code === room.code);
              return (
                <>
                  <div key={`label-${room.id}`} className="map-room-label">
                    <strong>{room.name}</strong>
                    <span>{room.code}</span>
                  </div>
                  <div key={`track-${room.id}`} className="map-room-track" style={{ gridColumn: `2 / span ${days.length || 1}` }}>
                    <div className="map-track-grid" style={{ gridTemplateColumns: `repeat(${days.length || 1}, minmax(64px, 1fr))` }}>
                      {days.map((day) => <div key={`${room.id}-${day}`} className="map-cell" />)}
                    </div>
                    {roomBlocks.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={`reservation-chip ${item.tone}`}
                        style={{ left: `calc(${(item.startIndex / (days.length || 1)) * 100}% + 6px)`, width: `calc(${(item.span / (days.length || 1)) * 100}% - 12px)` }}
                        onClick={() => setSelected(item)}
                      >
                        <strong>{item.guest_name || item.reservation.main_guest_name || "Reserva"}</strong>
                        <span>{item.reservation_code || `RES-${item.id}`} • {item.payment_status || "sem status"}</span>
                      </button>
                    ))}
                  </div>
                </>
              );
            })}
          </div>
        </div>
      </div>

      {selected ? (
        <div className="reservation-sidepanel-backdrop" onClick={() => setSelected(null)}>
          <div className="reservation-sidepanel card" onClick={(event) => event.stopPropagation()}>
            <div className="section-row">
              <div>
                <div className="eyebrow">Reserva selecionada</div>
                <h2 className="section-title">{selected.reservation.main_guest_name || selected.guest_name || "Reserva"}</h2>
                <div className="muted-line">{selected.reservation_code || `RES-${selected.id}`}</div>
              </div>
              <button className="button ghost" type="button" onClick={() => setSelected(null)}>Fechar</button>
            </div>

            <div className="detail-grid">
              <div className="detail-item"><span>Status PMS</span><strong>{selected.reservation.professional_status || selected.status}</strong></div>
              <div className="detail-item"><span>Pagamento</span><strong>{selected.payment_status || "-"}</strong></div>
              <div className="detail-item"><span>Período</span><strong>{selected.checkin || "-"} → {selected.checkout || "-"}</strong></div>
              <div className="detail-item"><span>Tipologia</span><strong>{selected.room_name}</strong></div>
              <div className="detail-item"><span>Valor</span><strong>{formatCurrency(Number(selected.total_value || selected.reservation.total_value || 0))}</strong></div>
              <div className="detail-item"><span>Origem</span><strong>{selected.source || selected.reservation.source || "-"}</strong></div>
              <div className="detail-item"><span>Telefone</span><strong>{selected.reservation.main_guest_phone || selected.reservation.guest_phone || "-"}</strong></div>
              <div className="detail-item"><span>Chegada prevista</span><strong>{selected.reservation.estimated_arrival || "-"}</strong></div>
              <div className="detail-item"><span>CPF</span><strong>{selected.reservation.guest_document || "-"}</strong></div>
              <div className="detail-item"><span>E-mail</span><strong>{selected.reservation.guest_email || "-"}</strong></div>
            </div>

            <div className="section-row"><h3 className="section-title">Hóspedes</h3></div>
            <div className="guest-stack">
              {(selected.reservation.guests || []).length ? selected.reservation.guests?.map((guest, index) => (
                <div className="guest-chip" key={`${guest.name || 'guest'}-${index}`}>
                  <strong>{guest.name || "Sem nome"}</strong>
                  <span>{guest.phone || guest.email || guest.cpf || "Sem contato"}</span>
                </div>
              )) : <div className="helper-box">Nenhum hóspede adicional informado.</div>}
            </div>

            {selected.reservation.notes_internal || selected.reservation.notes ? (
              <div className="section-row"><h3 className="section-title">Observações</h3></div>
            ) : null}
            {selected.reservation.notes_internal || selected.reservation.notes ? (
              <div className="notes-box">{selected.reservation.notes_internal || selected.reservation.notes}</div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>

      <style jsx global>{`
        .reservations-map-page { position: relative; }
        .reservations-map-toolbar { display: flex; justify-content: space-between; gap: 18px; align-items: end; }
        .toolbar-group { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; }
        .label.compact { min-width: 180px; }
        .toolbar-summary { display: flex; gap: 18px; flex-wrap: wrap; }
        .toolbar-summary div { display: grid; gap: 3px; }
        .toolbar-summary strong { font-size: 22px; }
        .toolbar-summary span { color: var(--muted); font-size: 13px; }
        .reservations-map-board { overflow: hidden; }
        .map-scroll { overflow-x: auto; padding-bottom: 8px; }
        .map-board { min-width: 1180px; display: grid; align-items: stretch; }
        .map-corner,
        .map-day-header,
        .map-room-label,
        .map-room-track { border-bottom: 1px solid rgba(148,163,184,.12); }
        .map-corner { position: sticky; left: 0; z-index: 5; padding: 16px; background: rgba(255,255,255,.03); border-right: 1px solid rgba(148,163,184,.12); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }
        .map-day-header { min-width: 64px; padding: 14px 8px; text-align: center; font-size: 12px; color: var(--muted); display: grid; gap: 4px; }
        .map-day-header strong { font-size: 15px; color: var(--text); }
        .map-room-label { position: sticky; left: 0; z-index: 4; background: rgba(8,17,29,.96); border-right: 1px solid rgba(148,163,184,.12); padding: 16px; display: grid; gap: 5px; align-content: center; }
        .map-room-label span { color: var(--muted); font-size: 12px; }
        .map-room-track { position: relative; min-height: 88px; }
        .map-track-grid { display: grid; min-height: 88px; }
        .map-cell { border-right: 1px solid rgba(148,163,184,.08); }
        .reservation-chip { position: absolute; top: 14px; height: 58px; border-radius: 18px; padding: 10px 12px; display: grid; align-content: center; text-align: left; gap: 3px; border: 1px solid rgba(255,255,255,.1); box-shadow: 0 14px 24px rgba(0,0,0,.22); cursor: pointer; transition: transform .18s ease, box-shadow .18s ease, opacity .18s ease; overflow: hidden; }
        .reservation-chip:hover { transform: translateY(-1px); box-shadow: 0 18px 32px rgba(0,0,0,.28); }
        .reservation-chip strong { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .reservation-chip span { font-size: 11px; opacity: .82; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .reservation-chip.is-confirmed { background: linear-gradient(135deg, rgba(16,185,129,.28), rgba(5,150,105,.2)); color: #d1fae5; border-color: rgba(16,185,129,.35); }
        .reservation-chip.is-pending { background: linear-gradient(135deg, rgba(245,158,11,.26), rgba(217,119,6,.18)); color: #fef3c7; border-color: rgba(245,158,11,.35); }
        .reservation-chip.is-problem { background: linear-gradient(135deg, rgba(239,68,68,.24), rgba(190,24,93,.18)); color: #fee2e2; border-color: rgba(239,68,68,.35); }
        .reservation-chip.is-blocked { background: linear-gradient(135deg, rgba(100,116,139,.28), rgba(51,65,85,.22)); color: #e2e8f0; border-color: rgba(148,163,184,.24); }
        .reservation-sidepanel-backdrop { position: fixed; inset: 0; background: rgba(2,6,23,.42); display: grid; justify-items: end; z-index: 60; padding: 20px; }
        .reservation-sidepanel { width: min(440px, 100%); height: calc(100vh - 40px); overflow: auto; border-radius: 28px; }
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 18px 0; }
        .detail-item { border: 1px solid rgba(148,163,184,.14); border-radius: 16px; padding: 12px; background: rgba(255,255,255,.02); display: grid; gap: 5px; }
        .detail-item span { color: var(--muted); font-size: 12px; }
        .guest-stack { display: grid; gap: 10px; }
        .guest-chip { border: 1px solid rgba(148,163,184,.14); border-radius: 16px; padding: 12px; background: rgba(255,255,255,.03); display: grid; gap: 4px; }
        .guest-chip span, .muted-line { color: var(--muted); font-size: 13px; }
        .notes-box { border-radius: 18px; border: 1px solid rgba(148,163,184,.14); background: rgba(255,255,255,.03); padding: 14px; color: #dbe5f2; white-space: pre-wrap; }
        @media (max-width: 900px) {
          .reservations-map-toolbar { flex-direction: column; align-items: stretch; }
          .toolbar-group { width: 100%; }
          .reservation-sidepanel-backdrop { justify-items: stretch; padding: 10px; }
          .reservation-sidepanel { width: 100%; height: auto; max-height: calc(100vh - 20px); }
          .detail-grid { grid-template-columns: 1fr; }
        }
      `}</style>
  );
}
