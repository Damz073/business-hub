export type HospitalitySummary = {
  conversas: { total: number; em_humano: number; em_bot: number };
  reservas: { total: number; leads_abertos: number; pagamentos_pendentes: number; receita_confirmada: number };
  inventario?: { tipos: number; unidades: number; tipos_ativos: number };
  inbox_recente: Array<{ id: number; customer_phone: string; customer_name?: string | null; status: string; assigned_to_name?: string | null; last_customer_message?: string | null; last_message_at?: string | null }>;
  reservas_recentes: Array<{ id: number; guest_name?: string | null; guest_phone: string; checkin_date?: string | null; checkout_date?: string | null; guest_count?: number | null; unit_category?: string | null; quoted_amount?: number | null; status: string; payment_status: string; updated_at?: string | null }>;
  inventory_snapshot?: Array<{ code: string; name: string; total: number; occupied_estimate: number; available_estimate: number; capacity: number; bed_setup: string; effective_rate: number }>;
  manual_rates?: Array<{ room_code: string; rate_value: number; valid_from: string; valid_until: string }>;
  settings?: Record<string, unknown> | null;
};

export type InboxItem = { id: number; customer_phone: string; customer_name?: string | null; channel: string; last_message_at?: string | null; status: string; assigned_to_phone?: string | null; assigned_to_name?: string | null; handoff_reason?: string | null; last_customer_message?: string | null; last_bot_message?: string | null; created_at?: string | null; updated_at?: string | null; };
export type ChatMessage = { id: number; direction: string; sender_type: string; sender_phone?: string | null; message_type: string; text_content?: string | null; created_at?: string | null; };
export type InboxResponse = { count: number; items: InboxItem[]; };
export type ChatMessagesResponse = { session_id: number; items: ChatMessage[]; };
export type ReservationItem = { id: number; guest_name?: string | null; guest_phone: string; checkin_date?: string | null; checkout_date?: string | null; guest_count?: number | null; unit_category?: string | null; quoted_amount?: number | null; status: string; payment_status: string; payment_reference?: string | null; human_confirmation_required?: number | boolean; finance_transaction_id?: number | null; source?: string | null; external_reservation_id?: string | null; sync_status?: string | null; notes?: string | null; created_at?: string | null; updated_at?: string | null; };
export type ReservationResponse = { count: number; items: ReservationItem[]; };
export type RoomTypeItem = { id: number; code: string; name: string; category?: string | null; capacity?: number | null; base_rate?: number | null; active?: number | boolean | null; notes?: string | null; quantity_total?: number | null; bed_setup?: string | null; max_adults?: number | null; max_children?: number | null; sort_order?: number | null; created_at?: string | null; updated_at?: string | null; };
export type RoomTypeResponse = { count: number; items: RoomTypeItem[]; };
export type ManualRateItem = { room_code: string; rate_value: number; valid_from: string; valid_until: string; };
export type ManualRateResponse = { count: number; items: ManualRateItem[]; status_text: string; };
export type InventoryItem = { code: string; name: string; total: number; occupied_estimate: number; available_estimate: number; capacity: number; bed_setup: string; effective_rate: number; };
export type InventoryResponse = { count: number; items: InventoryItem[]; };
export type BotSettings = {
  assistant_name?: string | null;
  welcome_message?: string | null;
  fallback_message?: string | null;
  pix_key?: string | null;
  payment_link_base?: string | null;
  human_handoff_enabled?: boolean | number | null;
  auto_reply_enabled?: boolean | number | null;
  reservations_module_enabled?: boolean | number | null;
  finance_module_enabled?: boolean | number | null;
  whatsapp_phone_number_id?: string | null;
  whatsapp_business_account_id?: string | null;
  whatsapp_verify_token?: string | null;
  checkin_time?: string | null;
  checkout_time?: string | null;
  reservation_payment_instructions?: string | null;
  hospitality_mode?: string | null;
  rate_collection_frequency?: string | null;
  rate_collection_time?: string | null;
  last_rate_prompt_at?: string | null;
  external_system_type?: string | null;
  omnibees_hotel_id?: string | null;
  omnibees_sync_enabled?: boolean | number | null;
  location_text?: string | null;
  maps_link?: string | null;
  pool_info?: string | null;
  garage_info?: string | null;
  breakfast_info?: string | null;
  pet_policy?: string | null;
  amenities_text?: string | null;
  fiscal_company_name?: string | null;
  fiscal_document?: string | null;
  fiscal_municipal_registration?: string | null;
  fiscal_service_city?: string | null;
  fiscal_email?: string | null;
  public_business_name?: string | null;
  public_contact_phone?: string | null;
  street_address?: string | null;
  neighborhood?: string | null;
  city_name?: string | null;
  state_code?: string | null;
  payment_alert_phones?: string | null;
};

export type HospitalityInboxList = InboxResponse;
export type HospitalityInboxDetail = ChatMessagesResponse;

export type OccupancyMapItem = {
  code: string;
  name: string;
  total: number;
  occupied_estimate: number;
  pending_estimate: number;
  blocked_estimate: number;
  available_estimate: number;
  capacity: number;
  bed_setup?: string;
  effective_rate?: number;
  occupancy_pct: number;
  occupancy_status: 'baixa' | 'media' | 'alta';
};

export type OccupancyMapResponse = {
  count: number;
  items: OccupancyMapItem[];
};
