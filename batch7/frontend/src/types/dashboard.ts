export type SummaryTransaction = {
  id: number;
  tipo: string;
  categoria: string;
  valor: number;
  descricao: string;
  criado_em: string;
};

export type DashboardSummary = {
  saldo_atual: number;
  total_entradas: number;
  total_despesas: number;
  quantidade_transacoes: number;
  mes_atual: {
    inicio: string;
    entradas: number;
    despesas: number;
    saldo: number;
    quantidade_transacoes: number;
  };
  ultimas_transacoes: SummaryTransaction[];
};
