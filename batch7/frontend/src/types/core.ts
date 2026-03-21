export type CoreOverview = {
  profile?: any;
  metrics: {
    conversations: number;
    customers: number;
    reservations: number;
    team_members: number;
  };
  growth_stage: string;
  saas_mode: string;
};

export type CustomerItem = {
  id: number;
  phone: string;
  name?: string | null;
  channel: string;
  customer_type: string;
  lifecycle_stage: string;
  last_message_at?: string | null;
  total_revenue?: number;
  notes?: string | null;
};

export type ModuleManifest = {
  key: string;
  label: string;
  description: string;
  core_features: string[];
  module_features: string[];
  icon: string;
  color: string;
};
