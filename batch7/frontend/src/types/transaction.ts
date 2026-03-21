export type TransactionItem = {
  id: number;
  restaurant_id: number;
  tipo: string;
  categoria: string;
  valor: number;
  descricao: string;
  criado_em: string;
  receipt_id?: number | null;
  merchant_id?: number | null;
};

export type TransactionListResponse = {
  count: number;
  items: TransactionItem[];
};
