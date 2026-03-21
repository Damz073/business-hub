export type AuthUser = {
  id: number;
  restaurant_id: number;
  restaurant_name: string;
  business_id?: number | null;
  business_name: string;
  business_type: string;
  name: string;
  email: string;
  role: string;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
};
