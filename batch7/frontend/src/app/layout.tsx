import './globals.css';

export const metadata = {
  title: 'Pousada Luz do Sol • Painel Operacional',
  description: 'Painel premium de operações, reservas, atendimento e financeiro da Pousada Luz do Sol',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang='pt-BR'>
      <body>{children}</body>
    </html>
  );
}
