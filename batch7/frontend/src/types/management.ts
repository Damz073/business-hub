export type CategoryItem = {
  name: string;
  transactions_count: number;
  merchants_count: number;
};

export type CategoryResponse = {
  count: number;
  items: CategoryItem[];
};

export type MerchantItem = {
  id: number;
  restaurant_id: number;
  display_name: string;
  normalized_name: string;
  default_category: string | null;
  occurrence_count: number;
  active: boolean;
  created_at: string | null;
  updated_at: string | null;
  last_seen_at: string | null;
};

export type MerchantResponse = {
  count: number;
  items: MerchantItem[];
};

export type RestaurantUserItem = {
  id: number;
  restaurant_id: number;
  telefone: string;
  nome: string;
  role: string;
  active: boolean;
  created_at: string | null;
};

export type RestaurantUserResponse = {
  count: number;
  items: RestaurantUserItem[];
};

export type RestaurantInfo = {
  restaurant_id: number;
  restaurant_name: string;
  status: string | null;
  plano: string | null;
  vencimento: string | null;
};


export type RestaurantUserRole = "admin" | "staff" | "financeiro" | "atendimento";
