"use client";
import { FormEvent, useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { BotSettings } from "@/types/hospitality";

export default function SettingsPage() { return <ProtectedPage>{() => <SettingsContent />}</ProtectedPage>; }

function SettingsContent() {
  const [form, setForm] = useState<BotSettings>({});
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => { apiFetch<BotSettings>("/hospitality/settings").then(setForm).catch((err) => setError(err.message || "Erro ao carregar configurações.")); }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError(""); setSuccess("");
    try {
      await apiFetch("/hospitality/settings", { method: "PUT", body: JSON.stringify(form) });
      setSuccess("Configurações salvas com sucesso.");
    } catch (err) { setError(err instanceof Error ? err.message : "Erro ao salvar configurações."); }
    finally { setSaving(false); }
  }

  return (
    <div className="page-grid">
      {error ? <div className="error-box">{error}</div> : null}
      {success ? <div className="helper-box">{success}</div> : null}

      <div className="split-grid">
        <div className="card fade-up">
          <h2 className="section-title">Bot & Pagamento</h2>
          <p className="inline-note">Configure comportamento do bot, Pix, mensagens padrão e parâmetros operacionais da pousada.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="two-col">
              <label className="label">Nome do assistente<input className="input" value={String(form.assistant_name || "")} onChange={(e) => setForm({ ...form, assistant_name: e.target.value })} /></label>
              <label className="label">Chave Pix<input className="input" value={String(form.pix_key || "")} onChange={(e) => setForm({ ...form, pix_key: e.target.value })} /></label>
              <label className="label">Link de pagamento<input className="input" value={String(form.payment_link_base || "")} onChange={(e) => setForm({ ...form, payment_link_base: e.target.value })} /></label>
              <label className="label">Modo de hospedagem<select className="input" value={String(form.hospitality_mode || "manual_rates")} onChange={(e) => setForm({ ...form, hospitality_mode: e.target.value })}><option value="manual_rates">manual_rates</option><option value="pms_integrated">pms_integrated</option></select></label>
              <label className="label">Coleta de tarifas<select className="input" value={String(form.rate_collection_frequency || "daily")} onChange={(e) => setForm({ ...form, rate_collection_frequency: e.target.value })}><option value="daily">daily</option><option value="weekly">weekly</option></select></label>
              <label className="label">Horário da coleta<input className="input" value={String(form.rate_collection_time || "08:00")} onChange={(e) => setForm({ ...form, rate_collection_time: e.target.value })} /></label>
              <label className="label">Check-in padrão<input className="input" value={String(form.checkin_time || "14:00")} onChange={(e) => setForm({ ...form, checkin_time: e.target.value })} /></label>
              <label className="label">Check-out padrão<input className="input" value={String(form.checkout_time || "12:00")} onChange={(e) => setForm({ ...form, checkout_time: e.target.value })} /></label>
              <label className="label">Auto reply ativo<select className="input" value={String(Number(Boolean(form.auto_reply_enabled)))} onChange={(e) => setForm({ ...form, auto_reply_enabled: e.target.value === "1" })}><option value="1">Sim</option><option value="0">Não</option></select></label>
              <label className="label">Handoff humano<select className="input" value={String(Number(Boolean(form.human_handoff_enabled)))} onChange={(e) => setForm({ ...form, human_handoff_enabled: e.target.value === "1" })}><option value="1">Sim</option><option value="0">Não</option></select></label>
            </div>
            <label className="label">Mensagem de boas-vindas<textarea className="input" value={String(form.welcome_message || "")} onChange={(e) => setForm({ ...form, welcome_message: e.target.value })} /></label>
            <label className="label">Mensagem fallback<textarea className="input" value={String(form.fallback_message || "")} onChange={(e) => setForm({ ...form, fallback_message: e.target.value })} /></label>
            <label className="label">Instruções de pagamento<textarea className="input" value={String(form.reservation_payment_instructions || "")} onChange={(e) => setForm({ ...form, reservation_payment_instructions: e.target.value })} /></label>
            <button className="button" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar configurações"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Meta Cloud API</h2>
          <p className="inline-note">O token de acesso permanece no .env do backend. Aqui ficam os dados operacionais da conta e do onboarding.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="label">Phone Number ID<input className="input" value={String(form.whatsapp_phone_number_id || "")} onChange={(e) => setForm({ ...form, whatsapp_phone_number_id: e.target.value })} /></label>
            <label className="label">WABA ID<input className="input" value={String(form.whatsapp_business_account_id || "")} onChange={(e) => setForm({ ...form, whatsapp_business_account_id: e.target.value })} /></label>
            <label className="label">Verify token do webhook<input className="input" value={String(form.whatsapp_verify_token || "")} onChange={(e) => setForm({ ...form, whatsapp_verify_token: e.target.value })} /></label>
            <label className="label">Sistema externo<select className="input" value={String(form.external_system_type || "none")} onChange={(e) => setForm({ ...form, external_system_type: e.target.value })}><option value="none">Nenhum</option><option value="omnibees">Omnibees</option></select></label>
            <label className="label">Hotel ID / referência Omnibees<input className="input" value={String(form.omnibees_hotel_id || "")} onChange={(e) => setForm({ ...form, omnibees_hotel_id: e.target.value })} /></label>
            <label className="label">Sync Omnibees<select className="input" value={String(Number(Boolean(form.omnibees_sync_enabled)))} onChange={(e) => setForm({ ...form, omnibees_sync_enabled: e.target.value === "1" })}><option value="0">Não</option><option value="1">Sim</option></select></label>
            <button className="button ghost" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar dados Cloud API"}</button>
          </form>
          <div className="helper-box" style={{ marginTop: 16 }}>
            <strong>Fluxos já preparados:</strong><br />
            • assumir/liberar atendimento pelo WhatsApp admin<br />
            • tarifas diárias ou semanais no modelo sem PMS<br />
            • reserva manual via WhatsApp para balcão e telefone<br />
            • base pronta para sync futura com a Omnibees
          </div>
        </div>


        <div className="card fade-up">
          <h2 className="section-title">Localização & Estrutura</h2>
          <p className="inline-note">Configure informações que o chatbot pode responder automaticamente, como localização, garagem, piscina e outras facilidades.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="label">Texto de localização<textarea className="input" value={String(form.location_text || "")} onChange={(e) => setForm({ ...form, location_text: e.target.value })} /></label>
            <label className="label">Link do Google Maps / localização<input className="input" value={String(form.maps_link || "")} onChange={(e) => setForm({ ...form, maps_link: e.target.value })} /></label>
            <label className="label">Garagem / estacionamento<textarea className="input" value={String(form.garage_info || "")} onChange={(e) => setForm({ ...form, garage_info: e.target.value })} /></label>
            <label className="label">Piscina<textarea className="input" value={String(form.pool_info || "")} onChange={(e) => setForm({ ...form, pool_info: e.target.value })} /></label>
            <label className="label">Café da manhã<textarea className="input" value={String(form.breakfast_info || "")} onChange={(e) => setForm({ ...form, breakfast_info: e.target.value })} /></label>
            <label className="label">Pets<textarea className="input" value={String(form.pet_policy || "")} onChange={(e) => setForm({ ...form, pet_policy: e.target.value })} /></label>
            <label className="label">Comodidades gerais<textarea className="input" value={String(form.amenities_text || "")} onChange={(e) => setForm({ ...form, amenities_text: e.target.value })} /></label>
            <button className="button ghost" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar localização & estrutura"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Marca, contato & white-label</h2>
          <p className="inline-note">Configure informações comerciais e de marca para reduzir customizações no código. O chatbot usa esses dados nas respostas e na apresentação da empresa.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <div className="two-col">
              <label className="label">Nome público da empresa<input className="input" value={String(form.public_business_name || "")} onChange={(e) => setForm({ ...form, public_business_name: e.target.value })} /></label>
              <label className="label">Telefone público / reservas<input className="input" value={String(form.public_contact_phone || "")} onChange={(e) => setForm({ ...form, public_contact_phone: e.target.value })} /></label>
              <label className="label">Endereço / rua<input className="input" value={String(form.street_address || "")} onChange={(e) => setForm({ ...form, street_address: e.target.value })} /></label>
              <label className="label">Bairro<input className="input" value={String(form.neighborhood || "")} onChange={(e) => setForm({ ...form, neighborhood: e.target.value })} /></label>
              <label className="label">Cidade<input className="input" value={String(form.city_name || "")} onChange={(e) => setForm({ ...form, city_name: e.target.value })} /></label>
              <label className="label">UF<input className="input" value={String(form.state_code || "")} onChange={(e) => setForm({ ...form, state_code: e.target.value })} /></label>
            </div>
            <label className="label">Telefones para alerta de pagamento<textarea className="input" value={String(form.payment_alert_phones || "")} onChange={(e) => setForm({ ...form, payment_alert_phones: e.target.value })} placeholder="557399999999, 557398888888" /></label>
            <button className="button ghost" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar dados de marca & contato"}</button>
          </form>
        </div>

        <div className="card fade-up">
          <h2 className="section-title">Dados fiscais</h2>
          <p className="inline-note">Prepare a base para emissão fiscal e operação da empresa sem precisar alterar código por cliente. A emissão em si pode ser ativada em uma próxima fase.</p>
          <form onSubmit={handleSubmit} className="form-grid">
            <label className="label">Razão social / nome fiscal<input className="input" value={String(form.fiscal_company_name || "")} onChange={(e) => setForm({ ...form, fiscal_company_name: e.target.value })} /></label>
            <label className="label">CNPJ / documento fiscal<input className="input" value={String(form.fiscal_document || "")} onChange={(e) => setForm({ ...form, fiscal_document: e.target.value })} /></label>
            <label className="label">Inscrição municipal<input className="input" value={String(form.fiscal_municipal_registration || "")} onChange={(e) => setForm({ ...form, fiscal_municipal_registration: e.target.value })} /></label>
            <label className="label">Cidade de prestação / emissão<input className="input" value={String(form.fiscal_service_city || "")} onChange={(e) => setForm({ ...form, fiscal_service_city: e.target.value })} /></label>
            <label className="label">Email fiscal<input className="input" value={String(form.fiscal_email || "")} onChange={(e) => setForm({ ...form, fiscal_email: e.target.value })} /></label>
            <button className="button ghost" type="submit" disabled={saving}>{saving ? "Salvando..." : "Salvar dados fiscais"}</button>
          </form>
        </div>

      </div>
    </div>
  );
}
