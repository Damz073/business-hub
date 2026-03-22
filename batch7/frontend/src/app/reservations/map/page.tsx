"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

type CalendarRoom = {
  id: number | string;
  name?: string;
  code?: string;
  category?: string;
};

type GuestInfo = {
  name?: string | null;
  phone?: string | null;
  email?: string | null;
  cpf?: string | null;
};

type CalendarReservation = {
  id: number | string;
  reservation_code?: string | null;
  room_id?: number | string | null;
  room_name?: string | null;
  room_label?: string | null;
  unit_category?: string | null;
  guest_name?: string | null;
  main_guest_name?: string | null;
  phone?: string | null;
  checkin?: string | null;
  checkout?: string | null;
  status?: string | null;
  calendar_status?: string | null;
  payment_status?: string | null;
  total_value?: number | null;
  notes_internal?: string | null;
  guests?: GuestInfo[];
  reservation?: {
    main_guest_name?: string | null;
    guest_name?: string | null;
    professional_status?: string | null;
    status?: string | null;
    source?: string | null;
    total_value?: number | null;
    main_guest_phone?: string | null;
    guest_phone?: string | null;
    estimated_arrival?: string | null;
    guest_document?: string | null;
    guest_email?: string | null;
    notes_internal?: string | null;
    notes?: string | null;
    guests?: GuestInfo[];
  };
};

type ReservationsCalendarResponse = {
  range?: {
    start_date?: string;
    end_date?: string;
  };
  start_date?: string;
  end_date?: string;
  count?: number;
  rooms?: CalendarRoom[];
  items?: CalendarReservation[];
};

type UiReservation = CalendarReservation & {
  roomKey: string;
  roomIndex: number;
  startIndex: number;
  span: number;
  tone: string;
  row: number;
};

type DragMode = "move" | "resize-left" | "resize-right";

type DraftChange = {
  roomKey: string;
  roomIndex: number;
  checkin: string;
  checkout: string;
};

type DragState = {
  id: string;
  mode: DragMode;
  pointerX: number;
  pointerY: number;
  originStartIndex: number;
  originSpan: number;
  originRoomIndex: number;
};

const DARK_THEME_SELECTOR = ":global(html.dark) &, :global(body.dark) &, :global([data-theme=\"dark\"]) &";

const DAY_WIDTH = 50;
const ROOM_LABEL_WIDTH = 208;
const ROW_HEIGHT = 56;
const ROW_GAP = 6;
const ROW_PITCH = ROW_HEIGHT + ROW_GAP;
const MAP_DAYS_BEFORE_TODAY = 3;
const MAP_DAYS_AFTER_TODAY = 28;

const statusToneMap: Record<string, string> = {
  confirmada: "is-confirmed",
  confirmed: "is-confirmed",
  checkin: "is-confirmed",
  checkout: "is-confirmed",
  hospedado: "is-confirmed",
  aguardando_pagamento: "is-pending",
  pending_payment: "is-pending",
  lead: "is-pending",
  pre_reserva: "is-pending",
  cancelada: "is-problem",
  cancelled: "is-problem",
  problem: "is-problem",
  bloqueada: "is-blocked",
  blocked: "is-blocked",
  manutencao: "is-blocked",
};

function addDays(date: Date, amount: number) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function toIsoDate(date: Date) {
  return date.toISOString().slice(0, 10);
}

function parseIso(value?: string | null) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDayLabel(value: string) {
  const date = new Date(`${value}T00:00:00`);
  return {
    weekday: date.toLocaleDateString("pt-BR", { weekday: "short" }),
    day: date.toLocaleDateString("pt-BR", { day: "2-digit" }),
    month: date.toLocaleDateString("pt-BR", { month: "short" }),
  };
}

function diffDays(start?: string | null, end?: string | null) {
  const a = parseIso(start);
  const b = parseIso(end);
  if (!a || !b) return 1;
  const value = Math.round((b.getTime() - a.getTime()) / 86400000);
  return Math.max(1, value || 1);
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function normalizeText(value?: string | null) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function displayGuestName(item: CalendarReservation) {
  return (
    item.main_guest_name ||
    item.guest_name ||
    item.reservation?.main_guest_name ||
    item.reservation?.guest_name ||
    "Reserva"
  );
}

function displayPhone(item: CalendarReservation) {
  return (
    item.phone ||
    item.reservation?.main_guest_phone ||
    item.reservation?.guest_phone ||
    "-"
  );
}

function displaySource(item: CalendarReservation) {
  return item.reservation?.source || "-";
}

function displayValue(item: CalendarReservation) {
  return Number(item.total_value || item.reservation?.total_value || 0);
}

function getTodayRange() {
  const today = new Date();
  return {
    start_date: toIsoDate(addDays(today, -MAP_DAYS_BEFORE_TODAY)),
    end_date: toIsoDate(addDays(today, MAP_DAYS_AFTER_TODAY)),
  };
}

function roomKeyOf(room: CalendarRoom) {
  return String(room.id ?? room.code ?? room.name ?? room.category ?? "room");
}

function createRoomMatcher(rooms: CalendarRoom[]) {
  return function resolveReservationRoom(item: CalendarReservation) {
    const explicitId = item.room_id != null ? String(item.room_id) : "";
    if (explicitId) {
      const byId = rooms.find((room) => String(room.id) === explicitId);
      if (byId) return byId;
    }

    const candidates = [item.room_name, item.room_label, item.unit_category]
      .filter(Boolean)
      .map((value) => normalizeText(value));

    return (
      rooms.find((room) => {
        const roomName = normalizeText(room.name);
        const roomCode = normalizeText(room.code);
        const roomCategory = normalizeText(room.category);
        return candidates.includes(roomName) || candidates.includes(roomCode) || candidates.includes(roomCategory);
      }) || rooms[0]
    );
  };
}

function toneLabel(tone: string) {
  if (tone === "is-confirmed") return "Confirmada";
  if (tone === "is-blocked") return "Bloqueio";
  if (tone === "is-problem") return "Atenção";
  return "Pendente";
}

export default function ReservationsMapPage() {
  return <ProtectedPage>{() => <ReservationsMapContent />}</ProtectedPage>;
}

function ReservationsMapContent() {
  const todayIso = useMemo(() => toIsoDate(new Date()), []);
  const [data, setData] = useState<ReservationsCalendarResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CalendarReservation | null>(null);
  const [hovered, setHovered] = useState<{
    item: CalendarReservation;
    x: number;
    y: number;
  } | null>(null);
  const [range, setRange] = useState(getTodayRange);
  const [drafts, setDrafts] = useState<Record<string, DraftChange>>({});
  const [drag, setDrag] = useState<DragState | null>(null);
  const gridRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const todayPinnedRef = useRef(false);
  const dragMovedRef = useRef(false);
  const suppressClickUntilRef = useRef(0);

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

  const rooms = data?.rooms || [];
  const calendarStart = data?.range?.start_date || data?.start_date || range.start_date;
  const calendarEnd = data?.range?.end_date || data?.end_date || range.end_date;

  const days = useMemo(() => {
    const list: string[] = [];
    let cursor = new Date(`${calendarStart}T00:00:00`);
    const end = new Date(`${calendarEnd}T00:00:00`);

    while (cursor <= end) {
      list.push(toIsoDate(cursor));
      cursor = addDays(cursor, 1);
    }

    return list;
  }, [calendarStart, calendarEnd]);

  const resolveRoom = useMemo(() => createRoomMatcher(rooms), [rooms]);

  const blocks = useMemo<UiReservation[]>(() => {
    return (data?.items || []).map((item) => {
      const room = resolveRoom(item);
      const roomKey = room ? roomKeyOf(room) : "unassigned";
      const roomIndex = Math.max(0, rooms.findIndex((entry) => roomKeyOf(entry) === roomKey));
      const draft = drafts[String(item.id)];
      const startDate = draft?.checkin || item.checkin || calendarStart;
      const endDate = draft?.checkout || item.checkout || calendarEnd;
      const startIndex = Math.max(0, days.findIndex((day) => day === startDate));
      const tone = statusToneMap[normalizeText(item.calendar_status || item.status || "lead")] || "is-pending";
      const span = Math.max(1, Math.min(diffDays(startDate, endDate), days.length || 1));

      return {
        ...item,
        roomKey: draft?.roomKey || roomKey,
        roomIndex: draft?.roomIndex ?? roomIndex,
        startIndex,
        span,
        tone,
        row: 0,
        checkin: startDate,
        checkout: endDate,
      };
    });
  }, [calendarEnd, calendarStart, data?.items, days, drafts, resolveRoom, rooms]);

  const blocksByRoom = useMemo(() => {
    const map = new Map<string, UiReservation[]>();

    for (const room of rooms) {
      map.set(roomKeyOf(room), []);
    }

    for (const item of blocks) {
      const key = item.roomKey;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(item);
    }

    map.forEach((items) => {
      items.sort((a, b) => a.startIndex - b.startIndex || a.span - b.span);
      const endByRow: number[] = [];
      items.forEach((item) => {
        let row = 0;
        while (row < endByRow.length && item.startIndex < endByRow[row]) row += 1;
        item.row = row;
        endByRow[row] = item.startIndex + item.span;
      });
    });

    return map;
  }, [blocks, rooms]);

  const occupancy = useMemo(() => {
    const totalCells = Math.max(1, rooms.length * Math.max(days.length, 1));
    const occupiedCells = blocks.reduce((sum, item) => sum + item.span, 0);
    return Math.min(100, Math.round((occupiedCells / totalCells) * 100));
  }, [blocks, rooms.length, days.length]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || todayPinnedRef.current || !days.length) return;
    const todayIndex = days.findIndex((day) => day === todayIso);
    if (todayIndex < 0) return;

    container.scrollLeft = Math.max(0, todayIndex * DAY_WIDTH - DAY_WIDTH * 1.5);
    todayPinnedRef.current = true;
  }, [days, todayIso]);

  useEffect(() => {
    if (!drag) return;
    setHovered(null);

    function onPointerMove(event: PointerEvent) {
      if (!gridRef.current) return;
      const rect = gridRef.current.getBoundingClientRect();
      const deltaX = event.clientX - drag.pointerX;
      const deltaY = event.clientY - drag.pointerY;
      if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) {
        dragMovedRef.current = true;
      }
      const relativeY = event.clientY - rect.top - 8;
      const dayShift = Math.round(deltaX / DAY_WIDTH);
      const nextRoomIndex = clamp(Math.floor(relativeY / ROW_PITCH), 0, Math.max(0, rooms.length - 1));

      setDrafts((current) => {
        const target = blocks.find((item) => String(item.id) === drag.id);
        if (!target) return current;

        let nextStartIndex = target.startIndex;
        let nextSpan = target.span;
        let nextCheckoutIndex = target.startIndex + target.span;

        if (drag.mode === "move") {
          nextStartIndex = clamp(drag.originStartIndex + dayShift, 0, Math.max(0, days.length - target.span));
          nextSpan = drag.originSpan;
          nextCheckoutIndex = nextStartIndex + nextSpan;
        }

        if (drag.mode === "resize-left") {
          const leftEdge = clamp(drag.originStartIndex + dayShift, 0, drag.originStartIndex + drag.originSpan - 1);
          nextStartIndex = leftEdge;
          nextCheckoutIndex = drag.originStartIndex + drag.originSpan;
          nextSpan = Math.max(1, nextCheckoutIndex - nextStartIndex);
        }

        if (drag.mode === "resize-right") {
          nextCheckoutIndex = clamp(
            drag.originStartIndex + drag.originSpan + dayShift,
            drag.originStartIndex + 1,
            days.length,
          );
          nextStartIndex = drag.originStartIndex;
          nextSpan = Math.max(1, nextCheckoutIndex - nextStartIndex);
        }

        const nextRoom = rooms[nextRoomIndex] || rooms[drag.originRoomIndex] || rooms[0];
        const nextRoomKey = nextRoom ? roomKeyOf(nextRoom) : target.roomKey;
        const nextCheckin = days[nextStartIndex] || target.checkin || calendarStart;
        const nextCheckout = days[nextStartIndex + nextSpan] || days[days.length - 1] || target.checkout || calendarEnd;

        return {
          ...current,
          [drag.id]: {
            roomKey: nextRoomKey,
            roomIndex: nextRoomIndex,
            checkin: nextCheckin,
            checkout: nextCheckout,
          },
        };
      });
    }

    function onPointerUp() {
      if (dragMovedRef.current) {
        suppressClickUntilRef.current = Date.now() + 250;
      }
      setDrag(null);
      window.setTimeout(() => {
        dragMovedRef.current = false;
      }, 0);
    }

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
    };
  }, [blocks, calendarEnd, calendarStart, days, drag, rooms]);

  function startInteraction(item: UiReservation, mode: DragMode, event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    dragMovedRef.current = false;
    (event.currentTarget as HTMLDivElement).setPointerCapture?.(event.pointerId);

    setDrag({
      id: String(item.id),
      mode,
      pointerX: event.clientX,
      pointerY: event.clientY,
      originStartIndex: item.startIndex,
      originSpan: item.span,
      originRoomIndex: item.roomIndex,
    });
  }

  function handleReservationClick(item: UiReservation) {
    if (dragMovedRef.current || Date.now() < suppressClickUntilRef.current) return;
    setSelected(item);
  }

  function resetToTodayWindow() {
    todayPinnedRef.current = false;
    setRange(getTodayRange());
  }

  const totalGridWidth = days.length * DAY_WIDTH;

  return (
    <>
      <section className="pms-map-page">
        <div className="pms-map-hero">
          <div>
            <span className="eyebrow">Fase 18 • mapa premium</span>
            <h1>Mapa de reservas estilo PMS, com interação visual real</h1>
            <p>
              Scroll lateral sem sobreposição, destaque do dia atual, preview profissional no hover e edição
              visual por arraste para operação mais rápida.
            </p>
          </div>

          <div className="hero-stats">
            <article>
              <strong>{data?.items?.length || 0}</strong>
              <span>reservas no período</span>
            </article>
            <article>
              <strong>{rooms.length}</strong>
              <span>quartos / tipologias</span>
            </article>
            <article>
              <strong>{occupancy}%</strong>
              <span>ocupação visual</span>
            </article>
          </div>
        </div>

        <div className="legend-row">
          <span className="legend-pill confirmed">Confirmada</span>
          <span className="legend-pill pending">Pendente</span>
          <span className="legend-pill blocked">Bloqueio</span>
          <span className="legend-pill problem">Atenção</span>
          <span className="legend-pill today">Hoje</span>
        </div>

        {error ? <div className="status-banner error">{error}</div> : null}
        {Object.keys(drafts).length ? (
          <div className="status-banner info">
            Ajustes visuais aplicados no mapa. Esta versão já deixa drag e resize prontos no front-end; se você
            quiser persistir no backend, eu conecto no próximo bloco.
          </div>
        ) : null}

        <div className="toolbar-card">
          <div className="toolbar-grid">
            <label>
              <span>Início</span>
              <input
                type="date"
                value={range.start_date}
                onChange={(event) => {
                  todayPinnedRef.current = false;
                  setRange((current) => ({ ...current, start_date: event.target.value }));
                }}
              />
            </label>

            <label>
              <span>Fim</span>
              <input
                type="date"
                value={range.end_date}
                onChange={(event) => {
                  todayPinnedRef.current = false;
                  setRange((current) => ({ ...current, end_date: event.target.value }));
                }}
              />
            </label>

            <button className="ghost-button" onClick={resetToTodayWindow} type="button">
              Ir para hoje
            </button>
            <button className="primary-button" onClick={load} type="button">
              {loading ? "Atualizando..." : "Atualizar mapa"}
            </button>
          </div>

          <div className="toolbar-meta">
            <span>{days.length} dias visíveis</span>
            <span>Janela inicial abre centralizada em hoje</span>
            <span>Drag move reserva • handles ajustam datas</span>
          </div>
        </div>

        <div className="map-shell">
          <div className="map-scroll" ref={scrollRef}>
            <div className="map-grid" style={{ width: Math.max(ROOM_LABEL_WIDTH + totalGridWidth, 0) }}>
              <div className="map-header sticky-room">Quartos / tipologias</div>

              <div className="map-header-days" style={{ width: totalGridWidth, minWidth: totalGridWidth }}>
                {days.map((day) => {
                  const label = formatDayLabel(day);
                  const isToday = day === todayIso;
                  return (
                    <div key={day} className={`day-header ${isToday ? "is-today" : ""}`} style={{ width: DAY_WIDTH }}>
                      <span>{label.weekday}</span>
                      <strong>{label.day}</strong>
                      <small>{label.month}</small>
                    </div>
                  );
                })}
              </div>

              <div className="rooms-column">
                {rooms.map((room, roomIndex) => {
                  const key = roomKeyOf(room);
                  const roomBlocks = blocksByRoom.get(key) || [];
                  const maxRows = Math.max(1, ...roomBlocks.map((item) => item.row + 1));
                  const roomHeight = maxRows * ROW_PITCH - ROW_GAP;

                  return (
                    <div className="room-sticky-cell" key={key} style={{ height: roomHeight }}>
                      <div className="room-name">{room.name || "Quarto"}</div>
                      <div className="room-meta">{room.code || room.category || "Sem identificação"}</div>
                      <div className="room-badges">
                        <span>{roomBlocks.length} reserva(s)</span>
                        <span>{roomIndex + 1}º da lista</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="grid-column" ref={gridRef} style={{ width: totalGridWidth, minWidth: totalGridWidth }}>
                {rooms.map((room) => {
                  const key = roomKeyOf(room);
                  const roomBlocks = blocksByRoom.get(key) || [];
                  const maxRows = Math.max(1, ...roomBlocks.map((item) => item.row + 1));
                  const roomHeight = maxRows * ROW_PITCH - ROW_GAP;

                  return (
                    <div className="room-grid-row" key={key} style={{ height: roomHeight }}>
                      <div className="room-day-grid">
                        {days.map((day) => (
                          <div key={`${key}-${day}`} className={`day-cell ${day === todayIso ? "is-today" : ""}`} style={{ width: DAY_WIDTH }} />
                        ))}
                      </div>

                      {roomBlocks.map((item) => {
                        const isDragging = drag?.id === String(item.id);
                        return (
                          <div
                            key={String(item.id)}
                            className={`reservation-card ${item.tone} ${isDragging ? "is-dragging" : ""}`}
                            style={{
                              left: item.startIndex * DAY_WIDTH + 6,
                              top: item.row * ROW_PITCH + 6,
                              width: item.span * DAY_WIDTH - 12,
                            }}
                            onClick={() => handleReservationClick(item)}
                            onMouseEnter={(event) => {
                              if (drag) return;
                              setHovered({ item, x: event.clientX + 18, y: event.clientY + 18 });
                            }}
                            onMouseMove={(event) => {
                              if (drag) return;
                              setHovered({ item, x: event.clientX + 18, y: event.clientY + 18 });
                            }}
                            onMouseLeave={() => setHovered((current) => (current?.item.id === item.id ? null : current))}
                          >
                            <div
                              className="resize-handle left"
                              onPointerDown={(event) => startInteraction(item, "resize-left", event)}
                            />

                            <div className="reservation-body" onPointerDown={(event) => startInteraction(item, "move", event)}>
                              <div className="reservation-topline">
                                <strong>{displayGuestName(item)}</strong>
                                <span>{toneLabel(item.tone)}</span>
                              </div>
                              <div className="reservation-meta">
                                <span>{item.reservation_code || `RES-${item.id}`}</span>
                                <span>{item.checkin} → {item.checkout}</span>
                              </div>
                              <div className="reservation-footer">
                                <span>{item.payment_status || "sem status"}</span>
                                <span>{formatCurrency(displayValue(item))}</span>
                              </div>
                            </div>

                            <div
                              className="resize-handle right"
                              onPointerDown={(event) => startInteraction(item, "resize-right", event)}
                            />
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {hovered ? (
          <div className="hover-card" style={{ left: hovered.x, top: hovered.y }}>
            <div className="hover-card__eyebrow">{hovered.item.reservation_code || `RES-${hovered.item.id}`}</div>
            <h3>{displayGuestName(hovered.item)}</h3>
            <p>
              {hovered.item.checkin || "-"} → {hovered.item.checkout || "-"}
            </p>
            <div className="hover-grid">
              <span>{hovered.item.room_name || hovered.item.room_label || hovered.item.unit_category || "Sem quarto"}</span>
              <span>{hovered.item.payment_status || "sem status"}</span>
              <span>{displaySource(hovered.item)}</span>
              <span>{formatCurrency(displayValue(hovered.item))}</span>
            </div>
          </div>
        ) : null}

        {selected ? (
          <div className="modal-backdrop" onClick={() => setSelected(null)}>
            <div className="modal-card" onClick={(event) => event.stopPropagation()}>
              <div className="modal-top">
                <div>
                  <span className="eyebrow">Reserva selecionada</span>
                  <h2>{displayGuestName(selected)}</h2>
                  <p>{selected.reservation_code || `RES-${selected.id}`}</p>
                </div>
                <button className="ghost-button" onClick={() => setSelected(null)} type="button">
                  Fechar
                </button>
              </div>

              <div className="modal-grid">
                <article>
                  <span>Status PMS</span>
                  <strong>{selected.reservation?.professional_status || selected.status || "-"}</strong>
                </article>
                <article>
                  <span>Pagamento</span>
                  <strong>{selected.payment_status || "-"}</strong>
                </article>
                <article>
                  <span>Período</span>
                  <strong>{selected.checkin || "-"} → {selected.checkout || "-"}</strong>
                </article>
                <article>
                  <span>Tipologia</span>
                  <strong>{selected.room_name || selected.room_label || selected.unit_category || "-"}</strong>
                </article>
                <article>
                  <span>Valor</span>
                  <strong>{formatCurrency(displayValue(selected))}</strong>
                </article>
                <article>
                  <span>Origem</span>
                  <strong>{displaySource(selected)}</strong>
                </article>
                <article>
                  <span>Telefone</span>
                  <strong>{displayPhone(selected)}</strong>
                </article>
                <article>
                  <span>Chegada prevista</span>
                  <strong>{selected.reservation?.estimated_arrival || "-"}</strong>
                </article>
                <article>
                  <span>CPF</span>
                  <strong>{selected.reservation?.guest_document || "-"}</strong>
                </article>
                <article>
                  <span>E-mail</span>
                  <strong>{selected.reservation?.guest_email || "-"}</strong>
                </article>
              </div>

              <div className="detail-section">
                <h3>Hóspedes</h3>
                <div className="guest-list">
                  {((selected.reservation?.guests || selected.guests) || []).length ? (
                    ((selected.reservation?.guests || selected.guests) || []).map((guest, index) => (
                      <div className="guest-item" key={`${guest.name || "guest"}-${index}`}>
                        <strong>{guest.name || "Sem nome"}</strong>
                        <span>{guest.phone || guest.email || guest.cpf || "Sem contato"}</span>
                      </div>
                    ))
                  ) : (
                    <div className="guest-item empty">Nenhum hóspede adicional informado.</div>
                  )}
                </div>
              </div>

              {selected.reservation?.notes_internal || selected.reservation?.notes || selected.notes_internal ? (
                <div className="detail-section">
                  <h3>Observações</h3>
                  <p>{selected.reservation?.notes_internal || selected.reservation?.notes || selected.notes_internal}</p>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      <style jsx global>{`
        .pms-map-page {
          --page-text: #132238;
          --page-muted: #64748b;
          --page-bg: linear-gradient(180deg, #f6f8fc 0%, #eef3f9 100%);
          --panel-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 249, 253, 0.98));
          --panel-border: rgba(148, 163, 184, 0.22);
          --panel-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
          --header-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 248, 252, 0.96));
          --room-bg: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(246, 249, 253, 0.98));
          --row-bg: linear-gradient(180deg, rgba(246, 249, 253, 0.9), rgba(241, 245, 249, 0.9));
          --grid-line: rgba(148, 163, 184, 0.16);
          --grid-line-soft: rgba(148, 163, 184, 0.1);
          --today-bg: linear-gradient(180deg, rgba(59, 130, 246, 0.14), rgba(37, 99, 235, 0.06));
          --today-outline: rgba(59, 130, 246, 0.24);
          --input-bg: rgba(255, 255, 255, 0.9);
          --button-ghost-bg: rgba(255, 255, 255, 0.85);
          --glass-bg: rgba(255, 255, 255, 0.68);
          padding: 14px;
          color: var(--page-text);
          background: var(--page-bg);
          height: calc(100vh - 112px);
          min-height: calc(100vh - 112px);
          width: 100%;
          max-width: 100%;
          overflow: hidden;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        ${DARK_THEME_SELECTOR} {
          --page-text: #e7edf7;
          --page-muted: #9db0d3;
          --page-bg: radial-gradient(circle at top left, rgba(76, 120, 255, 0.18), transparent 26%), linear-gradient(180deg, #07111f 0%, #0b1422 40%, #09111b 100%);
          --panel-bg: linear-gradient(180deg, rgba(14, 23, 39, 0.96), rgba(10, 17, 29, 0.96));
          --panel-border: rgba(160, 181, 230, 0.14);
          --panel-shadow: 0 18px 46px rgba(2, 6, 18, 0.4);
          --header-bg: linear-gradient(180deg, rgba(8, 15, 28, 0.98), rgba(9, 17, 30, 0.96));
          --room-bg: linear-gradient(180deg, rgba(12, 20, 34, 0.98), rgba(10, 17, 29, 0.98));
          --row-bg: linear-gradient(180deg, rgba(8, 13, 22, 0.75), rgba(9, 14, 24, 0.75));
          --grid-line: rgba(160, 181, 230, 0.12);
          --grid-line-soft: rgba(160, 181, 230, 0.08);
          --today-bg: linear-gradient(180deg, rgba(59, 130, 246, 0.18), rgba(37, 99, 235, 0.08));
          --today-outline: rgba(96, 165, 250, 0.28);
          --input-bg: rgba(255, 255, 255, 0.04);
          --button-ghost-bg: rgba(255, 255, 255, 0.04);
          --glass-bg: rgba(255, 255, 255, 0.03);
        }



        .pms-map-page > * {
          min-width: 0;
          max-width: 100%;
        }

        .pms-map-page .toolbar-card,
        .pms-map-page .status-banner,
        .pms-map-page .legend-row {
          flex: 0 0 auto;
        }

        .pms-map-hero,
        .toolbar-card,
        .map-shell {
          min-width: 0;
          max-width: 100%;
          border: 1px solid var(--panel-border);
          background: var(--panel-bg);
          box-shadow: var(--panel-shadow);
          border-radius: 24px;
        }

        .pms-map-hero {
          display: flex;
          gap: 12px;
          justify-content: space-between;
          align-items: flex-start;
          padding: 16px 18px;
          margin-bottom: 0;
          flex: 0 0 auto;
        }

        .pms-map-hero h1 {
          margin: 6px 0 8px;
          font-size: clamp(1.65rem, 2.5vw, 2.35rem);
          line-height: 1.02;
          max-width: 760px;
        }

        .pms-map-hero p {
          margin: 0;
          color: var(--page-muted);
          line-height: 1.45;
          max-width: 780px;
          font-size: 0.94rem;
        }

        .eyebrow {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          letter-spacing: 0.12em;
          text-transform: uppercase;
          font-size: 0.72rem;
          color: #85a7ff;
          font-weight: 700;
        }

        .hero-stats {
          display: grid;
          grid-template-columns: repeat(3, minmax(108px, 1fr));
          gap: 10px;
          min-width: 330px;
        }

        .hero-stats article,
        .modal-grid article,
        .guest-item,
        .hover-card {
          border: 1px solid rgba(158, 180, 229, 0.12);
          background: var(--glass-bg);
          backdrop-filter: blur(12px);
        }

        .hero-stats article {
          border-radius: 14px;
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .hero-stats strong {
          font-size: 1.35rem;
          line-height: 1;
        }

        .hero-stats span,
        .toolbar-meta,
        .room-meta,
        .room-badges,
        .reservation-meta,
        .reservation-footer,
        .modal-card p,
        .detail-section p,
        .guest-item span,
        .hover-grid,
        .hover-card p {
          color: var(--page-muted);
        }

        .legend-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin: 0;
          flex: 0 0 auto;
        }

        .legend-pill {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: 6px 10px;
          font-size: 0.76rem;
          border: 1px solid transparent;
          background: var(--button-ghost-bg);
        }

        .legend-pill.confirmed { background: rgba(45, 212, 191, 0.13); border-color: rgba(45, 212, 191, 0.28); }
        .legend-pill.pending { background: rgba(250, 204, 21, 0.13); border-color: rgba(250, 204, 21, 0.28); }
        .legend-pill.blocked { background: rgba(168, 85, 247, 0.13); border-color: rgba(168, 85, 247, 0.28); }
        .legend-pill.problem { background: rgba(248, 113, 113, 0.13); border-color: rgba(248, 113, 113, 0.28); }
        .legend-pill.today { background: rgba(96, 165, 250, 0.14); border-color: rgba(96, 165, 250, 0.32); }

        .status-banner {
          margin: 0;
          padding: 8px 10px;
          border-radius: 14px;
          border: 1px solid rgba(158, 180, 229, 0.14);
          font-size: 0.86rem;
          flex: 0 0 auto;
        }

        .status-banner.error {
          background: rgba(127, 29, 29, 0.3);
          color: #fecaca;
        }

        .status-banner.info {
          background: rgba(15, 118, 110, 0.18);
          color: #c7f9f1;
        }

        .toolbar-card {
          padding: 14px;
          margin-bottom: 0;
          flex: 0 0 auto;
        }

        .toolbar-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
          gap: 10px;
          align-items: end;
        }



        .toolbar-grid > * {
          width: 100%;
          min-width: 0;
        }

        .toolbar-grid label {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .toolbar-grid span {
          font-size: 0.84rem;
          color: var(--page-muted);
        }

        .toolbar-grid input,
        .primary-button,
        .ghost-button {
          height: 40px;
          border-radius: 12px;
          border: 1px solid rgba(160, 181, 230, 0.16);
          padding: 0 12px;
          font: inherit;
        }

        .toolbar-grid input {
          background: var(--button-ghost-bg);
          color: var(--page-text);
        }

        .primary-button,
        .ghost-button {
          cursor: pointer;
          transition: transform 0.16s ease, border-color 0.16s ease, background 0.16s ease;
        }

        .primary-button {
          background: linear-gradient(135deg, #4f7cff, #2f5ef7);
          color: white;
          border-color: rgba(110, 146, 255, 0.45);
        }

        .ghost-button {
          background: var(--button-ghost-bg);
          color: var(--page-text);
        }



        .primary-button,
        .ghost-button {
          min-width: 0;
          justify-self: stretch;
          white-space: nowrap;
          font-size: 0.92rem;
        }

        .primary-button:hover,
        .ghost-button:hover {
          transform: translateY(-1px);
        }

        .toolbar-meta {
          display: flex;
          gap: 12px;
          flex-wrap: wrap;
          margin-top: 10px;
          font-size: 0.78rem;
        }

        .map-shell {
          overflow: hidden;
          position: relative;
          width: 100%;
          max-width: 100%;
          min-height: 0;
          height: auto;
          flex: 1 1 auto;
        }

        .map-scroll {
          overflow: auto;
          overscroll-behavior: contain;
          width: 100%;
          max-width: 100%;
          height: 100%;
        }



        .map-scroll::-webkit-scrollbar {
          height: 12px;
          width: 12px;
        }

        .map-scroll::-webkit-scrollbar-thumb {
          background: rgba(148, 163, 184, 0.45);
          border-radius: 999px;
          border: 3px solid transparent;
          background-clip: padding-box;
        }

        .map-scroll::-webkit-scrollbar-track {
          background: transparent;
        }

        .map-grid {
          display: grid;
          grid-template-columns: ${ROOM_LABEL_WIDTH}px 1fr;
          align-items: start;
        }

        .map-header,
        .map-header-days {
          position: sticky;
          top: 0;
          z-index: 20;
          min-height: 60px;
          background: var(--header-bg);
          border-bottom: 1px solid var(--grid-line);
        }

        .map-header {
          display: flex;
          align-items: center;
          padding: 0 12px;
          font-weight: 700;
          font-size: 0.95rem;
          color: var(--page-text);
        }

        .sticky-room,
        .room-sticky-cell {
          position: sticky;
          left: 0;
          z-index: 18;
        }

        .map-header.sticky-room {
          z-index: 24;
        }

        .map-header-days {
          display: flex;
          z-index: 22;
        }

        .day-header {
          flex: 0 0 auto;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          gap: 1px;
          border-left: 1px solid var(--grid-line-soft);
          color: var(--page-muted);
          font-size: 0.72rem;
        }

        .day-header strong {
          color: var(--page-text);
          font-size: 0.98rem;
          line-height: 1;
        }

        .day-header.is-today {
          background: var(--today-bg);
          box-shadow: inset 0 0 0 1px var(--today-outline);
        }

        .rooms-column,
        .grid-column {
          display: grid;
          grid-auto-rows: auto;
        }

        .room-sticky-cell {
          border-right: 1px solid var(--grid-line);
          border-bottom: 1px solid var(--grid-line-soft);
          background: var(--room-bg);
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 4px;
        }

        .room-name {
          font-weight: 700;
          font-size: 0.92rem;
          color: var(--page-text);
        }

        .room-badges {
          display: flex;
          gap: 5px;
          flex-wrap: wrap;
          font-size: 0.7rem;
        }

        .room-badges span {
          padding: 4px 7px;
          border-radius: 999px;
          background: rgba(255, 255, 255, 0.05);
        }

        .grid-column {
          position: relative;
        }

        .room-grid-row {
          position: relative;
          border-bottom: 1px solid var(--grid-line-soft);
          background: var(--row-bg);
        }

        .room-day-grid {
          position: absolute;
          inset: 0;
          display: flex;
        }

        .day-cell {
          flex: 0 0 auto;
          height: 100%;
          border-left: 1px solid var(--grid-line-soft);
          background: transparent;
        }

        .day-cell.is-today {
          background: var(--today-bg);
          box-shadow: inset 0 0 0 1px var(--today-outline);
        }

        .reservation-card {
          position: absolute;
          user-select: none;
          touch-action: none;
          height: ${ROW_HEIGHT - 8}px;
          border-radius: 14px;
          display: grid;
          grid-template-columns: 8px 1fr 8px;
          align-items: stretch;
          cursor: pointer;
          overflow: hidden;
          border: 1px solid transparent;
          box-shadow: 0 16px 40px rgba(3, 7, 18, 0.34);
          backdrop-filter: blur(12px);
          transition: transform 0.14s ease, box-shadow 0.14s ease, opacity 0.14s ease;
        }

        .reservation-card:hover {
          transform: translateY(-1px);
          box-shadow: 0 18px 44px rgba(3, 7, 18, 0.42);
        }

        .reservation-card.is-dragging {
          opacity: 0.9;
          box-shadow: 0 22px 52px rgba(31, 82, 201, 0.34);
        }

        .reservation-card.is-confirmed {
          background: linear-gradient(135deg, rgba(14, 116, 144, 0.95), rgba(13, 148, 136, 0.95));
          border-color: rgba(153, 246, 228, 0.22);
        }

        .reservation-card.is-pending {
          background: linear-gradient(135deg, rgba(180, 83, 9, 0.95), rgba(217, 119, 6, 0.95));
          border-color: rgba(253, 224, 71, 0.22);
        }

        .reservation-card.is-blocked {
          background: linear-gradient(135deg, rgba(109, 40, 217, 0.95), rgba(124, 58, 237, 0.95));
          border-color: rgba(216, 180, 254, 0.24);
        }

        .reservation-card.is-problem {
          background: linear-gradient(135deg, rgba(185, 28, 28, 0.95), rgba(220, 38, 38, 0.95));
          border-color: rgba(252, 165, 165, 0.24);
        }

        .resize-handle {
          position: relative;
          cursor: ew-resize;
          background: rgba(255, 255, 255, 0.18);
        }

        .resize-handle::after {
          content: "";
          position: absolute;
          top: 18px;
          bottom: 18px;
          width: 2px;
          background: rgba(255, 255, 255, 0.8);
          border-radius: 99px;
        }

        .resize-handle.left::after { left: 4px; }
        .resize-handle.right::after { right: 4px; }

        .reservation-body {
          padding: 8px 10px;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          gap: 4px;
          color: #fff;
          cursor: grab;
        }

        .reservation-body:active {
          cursor: grabbing;
        }

        .reservation-topline,
        .reservation-meta,
        .reservation-footer,
        .hover-grid {
          display: flex;
          justify-content: space-between;
          gap: 10px;
        }

        .reservation-topline strong {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .reservation-topline span,
        .reservation-meta span,
        .reservation-footer span {
          font-size: 0.7rem;
          white-space: nowrap;
        }

        .hover-card {
          position: fixed;
          color: var(--page-text);
          z-index: 60;
          width: 260px;
          padding: 14px;
          border-radius: 16px;
          box-shadow: 0 24px 64px rgba(1, 6, 19, 0.48);
          pointer-events: none;
          background: color-mix(in srgb, var(--room-bg) 92%, black 8%);
        }

        .hover-card__eyebrow {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #88a8ff;
          margin-bottom: 6px;
        }

        .hover-card h3 {
          margin: 0 0 4px;
          font-size: 1rem;
        }

        .hover-card p {
          margin: 0 0 10px;
          font-size: 0.88rem;
        }

        .hover-grid {
          flex-wrap: wrap;
          font-size: 0.8rem;
        }

        .hover-grid span {
          width: calc(50% - 5px);
        }

        .modal-backdrop {
          position: fixed;
          inset: 0;
          z-index: 70;
          display: grid;
          place-items: center;
          padding: 22px;
          background: rgba(4, 10, 19, 0.72);
          backdrop-filter: blur(8px);
        }

        .modal-card {
          width: min(920px, 100%);
          color: var(--page-text);
          max-height: calc(100vh - 44px);
          overflow: auto;
          border-radius: 24px;
          padding: 20px;
          border: 1px solid var(--panel-border);
          background: var(--panel-bg);
          box-shadow: 0 24px 64px rgba(2, 6, 18, 0.24);
        }

        .modal-top {
          display: flex;
          justify-content: space-between;
          gap: 12px;
          align-items: flex-start;
          margin-bottom: 14px;
        }

        .modal-top h2 {
          margin: 8px 0 4px;
          font-size: 1.8rem;
        }

        .modal-grid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .modal-grid article,
        .guest-item {
          border-radius: 16px;
          padding: 14px;
        }

        .modal-grid span,
        .detail-section h3 {
          color: var(--page-muted);
          display: block;
          margin-bottom: 8px;
          font-size: 0.83rem;
        }

        .detail-section {
          margin-top: 18px;
        }

        .detail-section h3 {
          text-transform: uppercase;
          letter-spacing: 0.08em;
        }

        .guest-list {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
        }

        .guest-item.empty {
          color: var(--page-muted);
        }

        @media (max-width: 1100px) {
          .pms-map-page {
            height: auto;
            min-height: calc(100vh - 96px);
            overflow: visible;
          }

          .pms-map-hero {
            flex-direction: column;
          }

          .hero-stats {
            min-width: 0;
            width: 100%;
          }

          .toolbar-grid {
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          }
        }

        @media (max-width: 720px) {
          .pms-map-page {
            padding: 12px;
            height: auto;
            min-height: auto;
            overflow: visible;
          }

          .map-shell {
            min-height: 360px;
            height: auto;
          }

          .hero-stats,
          .modal-grid,
          .guest-list,
          .toolbar-grid {
            grid-template-columns: 1fr;
          }

          .map-grid {
            grid-template-columns: 200px 1fr;
          }
        }
      `}</style>
    </>
  );
}
