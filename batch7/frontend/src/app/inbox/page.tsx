"use client";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { ChatMessagesResponse, InboxItem, InboxResponse } from "@/types/hospitality";

export default function InboxPage() {
  return <ProtectedPage>{() => <InboxContent />}</ProtectedPage>;
}

function InboxContent() {
  const [data, setData] = useState<InboxResponse | null>(null);
  const [selected, setSelected] = useState<InboxItem | null>(null);
  const [messages, setMessages] = useState<ChatMessagesResponse | null>(null);
  const [replyText, setReplyText] = useState("");
  const [error, setError] = useState("");
  const [loadingInbox, setLoadingInbox] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [acting, setActing] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const selectedIdRef = useRef<number | null>(null);
  const lastMessageFingerprintRef = useRef("");
  const shouldStickToBottomRef = useRef(true);

  function fingerprintMessages(payload: ChatMessagesResponse | null) {
    if (!payload?.items?.length) return "empty";
    const tail = payload.items.slice(-5).map((item) => `${item.id}:${item.created_at}:${item.text_content || ""}`).join("|");
    return `${payload.items.length}:${tail}`;
  }

  function mergeSelected(items: InboxItem[], preferredId?: number) {
    if (!items.length) return null;
    const targetId = preferredId || selectedIdRef.current || selected?.id;
    return (targetId ? items.find((item) => item.id === targetId) : null) || items[0];
  }

  async function loadInbox(preferredId?: number, silent = false) {
    if (!silent) setLoadingInbox(true);
    const payload = await apiFetch<InboxResponse>("/hospitality/inbox");
    setError("");
    setData((prev) => {
      const same = JSON.stringify(prev?.items || []) === JSON.stringify(payload.items || []);
      return same ? prev : payload;
    });

    if (!payload.items.length) {
      setSelected(null);
      setMessages(null);
      selectedIdRef.current = null;
      if (!silent) setLoadingInbox(false);
      return;
    }

    const chosen = mergeSelected(payload.items, preferredId);
    selectedIdRef.current = chosen?.id || null;
    setSelected((prev) => {
      if (!chosen) return null;
      if (
        prev &&
        prev.id === chosen.id &&
        prev.status === chosen.status &&
        prev.last_message_at === chosen.last_message_at &&
        prev.last_customer_message === chosen.last_customer_message &&
        prev.last_bot_message === chosen.last_bot_message &&
        prev.assigned_to_name === chosen.assigned_to_name
      ) {
        return prev;
      }
      return chosen;
    });
    if (!silent) setLoadingInbox(false);
  }

  async function loadMessages(sessionId: number, silent = false) {
    if (!silent) setLoadingMessages(true);
    try {
      const payload = await apiFetch<ChatMessagesResponse>(`/hospitality/inbox/${sessionId}/messages`);
      const nextFingerprint = fingerprintMessages(payload);
      const changed = nextFingerprint !== lastMessageFingerprintRef.current;
      lastMessageFingerprintRef.current = nextFingerprint;
      setMessages((prev) => {
        const same = JSON.stringify(prev?.items || []) === JSON.stringify(payload.items || []);
        return same ? prev : payload;
      });
      setError("");
      if (changed) {
        requestAnimationFrame(() => {
          if (!scrollRef.current) return;
          const el = scrollRef.current;
          el.scrollTop = el.scrollHeight;
        });
      }
    } catch (err: unknown) {
      if (!silent) {
        setMessages({ session_id: sessionId, items: [] });
        setError(err instanceof Error ? err.message : "Erro ao carregar conversa.");
      }
    } finally {
      if (!silent) setLoadingMessages(false);
    }
  }

  useEffect(() => {
    loadInbox(undefined, false).catch((err: unknown) => {
      setLoadingInbox(false);
      setError(err instanceof Error ? err.message : "Erro ao carregar inbox.");
    });
  }, []);

  useEffect(() => {
    if (!selected?.id) return;
    selectedIdRef.current = selected.id;
    shouldStickToBottomRef.current = true;
    loadMessages(selected.id, false);
  }, [selected?.id]);

  useEffect(() => {
    if (!selected?.id) return;
    const interval = window.setInterval(() => {
      const currentId = selectedIdRef.current;
      loadInbox(currentId || selected.id, true).catch(() => undefined);
      loadMessages(currentId || selected.id, true).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(interval);
  }, [selected?.id]);

  useEffect(() => {
    if (!scrollRef.current) return;
    const el = scrollRef.current;
    const onScroll = () => {
      const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      shouldStickToBottomRef.current = nearBottom;
    };
    el.addEventListener("scroll", onScroll);
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!scrollRef.current || !messages) return;
    const el = scrollRef.current;
    if (shouldStickToBottomRef.current) {
      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight;
      });
    }
  }, [messages]);

  async function assume() {
    if (!selected) return;
    setActing(true);
    try {
      await apiFetch(`/hospitality/inbox/${selected.id}/assume`, { method: "POST" });
      await loadInbox(selected.id, true);
      await loadMessages(selected.id, true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao assumir atendimento.");
    } finally {
      setActing(false);
    }
  }

  async function release() {
    if (!selected) return;
    setActing(true);
    try {
      await apiFetch(`/hospitality/inbox/${selected.id}/release`, { method: "POST" });
      await loadInbox(selected.id, true);
      await loadMessages(selected.id, true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao devolver conversa ao bot.");
    } finally {
      setActing(false);
    }
  }

  async function reply(event: FormEvent) {
    event.preventDefault();
    if (!selected || !replyText.trim()) return;
    setActing(true);
    try {
      await apiFetch(`/hospitality/inbox/${selected.id}/reply`, {
        method: "POST",
        body: JSON.stringify({ text: replyText.trim() }),
      });
      setReplyText("");
      await loadInbox(selected.id, true);
      await loadMessages(selected.id, true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao enviar mensagem.");
    } finally {
      setActing(false);
    }
  }

  const stats = useMemo(
    () => ({
      total: data?.items.length || 0,
      human: data?.items.filter((item) => item.status === "human_active").length || 0,
      bot: data?.items.filter((item) => item.status === "bot_active").length || 0,
    }),
    [data],
  );

  return (
    <div className="page-grid">
      <div className="cards-grid">
        <div className="card metric-card"><div className="metric-kicker">Inbox</div><div className="metric-title">Conversas</div><div className="metric-value">{stats.total}</div><div className="metric-subtitle">Central operacional do WhatsApp</div></div>
        <div className="card metric-card"><div className="metric-kicker">Humano</div><div className="metric-title">Atendimento assumido</div><div className="metric-value">{stats.human}</div><div className="metric-subtitle">Conversas sob controle manual</div></div>
        <div className="card metric-card"><div className="metric-kicker">Bot</div><div className="metric-title">Automação ativa</div><div className="metric-value">{stats.bot}</div><div className="metric-subtitle">Atendimentos prontos para IA</div></div>
      </div>

      {error ? <div className="error-box">{error}</div> : null}

      <div className="split-grid split-grid-inbox">
        <div className="card fade-up conversation-list">
          <div className="section-row"><h2 className="section-title">Conversas</h2><div className="pill info">Clique para abrir</div></div>
          <div className="message-list" style={{ marginTop: 12 }}>
            {loadingInbox && !data ? <div className="empty-state-mini">Carregando conversas…</div> : null}
            {(data?.items || []).map((item) => {
              const title = item.customer_name || item.customer_phone;
              const active = selected?.id === item.id;
              return (
                <button type="button" key={item.id} className={`conversation-item ${active ? "active" : ""}`} onClick={() => { selectedIdRef.current = item.id; setSelected(item); setError(""); }}>
                  <div className="section-row">
                    <strong>{title}</strong>
                    <span className={`pill ${item.status === "human_active" ? "warning" : item.status === "human_requested" ? "info" : "success"}`}>{item.status}</span>
                  </div>
                  <div className="inline-note" style={{ marginTop: 6 }}>{item.customer_phone} • {formatDateTime(item.last_message_at)}</div>
                  <div style={{ marginTop: 10 }}>{item.last_customer_message || item.last_bot_message || "Sem mensagem recente"}</div>
                </button>
              );
            })}
            {!loadingInbox && !data?.items.length ? <div className="empty-state-mini">Nenhuma conversa registrada ainda.</div> : null}
          </div>
        </div>

        <div className="card fade-up">
          {selected ? (
            <>
              <div className="chat-header">
                <div className="chat-header-main">
                  <div className="chat-avatar">{(selected.customer_name || selected.customer_phone).slice(0, 1).toUpperCase()}</div>
                  <div>
                    <div style={{ fontWeight: 700 }}>{selected.customer_name || selected.customer_phone}</div>
                    <div className="chat-phone">{selected.customer_phone} • {selected.assigned_to_name || "Sem responsável"}</div>
                  </div>
                </div>
                <div className="stat-inline">
                  <button type="button" className="button warning" onClick={assume} disabled={acting}>Assumir</button>
                  <button type="button" className="button ghost" onClick={release} disabled={acting}>Devolver ao bot</button>
                </div>
              </div>

              <div className="chat-thread whatsapp-thread" ref={scrollRef}>
                {loadingMessages && !messages ? (
                  <div className="chat-loading">Carregando mensagens…</div>
                ) : messages?.items?.length ? (
                  <div className="message-list whatsapp-message-list">
                    {messages.items.map((msg) => (
                      <div key={msg.id} className={`message-bubble ${msg.direction === "inbound" ? "inbound" : "outbound"}`}>
                        <div>{msg.text_content || "[sem conteúdo]"}</div>
                        <div className="message-meta">{formatDateTime(msg.created_at)}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="chat-empty-state">Esta conversa ainda não possui mensagens renderizáveis.</div>
                )}
              </div>

              <form onSubmit={reply} className="chat-compose whatsapp-compose">
                <label className="label">Mensagem manual<textarea className="input chat-input" value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="Digite uma mensagem para o hóspede" /></label>
                <button className="button" type="submit" disabled={acting || !replyText.trim()}>Enviar mensagem</button>
              </form>
            </>
          ) : (
            <div className="inline-note">Selecione uma conversa para ver o histórico.</div>
          )}
        </div>
      </div>
    </div>
  );
}
