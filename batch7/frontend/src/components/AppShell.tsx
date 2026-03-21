"use client";
import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { logout } from "@/lib/auth";
import { getBrandingForBusiness } from "@/lib/branding";
import { AuthUser } from "@/types/auth";

const THEME_KEY = "business-hub-theme";

type ThemeMode = "dark" | "light";

function getLinks(businessType: string) {
  const common = [
    { href: "/dashboard", label: "Dashboard", emoji: "◈" },
    { href: "/transactions", label: "Financeiro", emoji: "◌" },
  ];
  if (businessType === "hospitality") {
    return [
      { href: "/dashboard", label: "Dashboard", emoji: "◈" },
      { href: "/inbox", label: "Inbox", emoji: "◎" },
      { href: "/reservations", label: "Reservas", emoji: "◍" },
      { href: "/reservations/map", label: "Mapa PMS", emoji: "◫" },
      { href: "/rooms", label: "Quartos", emoji: "▣" },
      { href: "/transactions", label: "Financeiro", emoji: "◌" },
      { href: "/crm", label: "CRM", emoji: "◒" },
      { href: "/business", label: "Negócio", emoji: "◧" },
      { href: "/settings", label: "Bot & Pagamento", emoji: "◇" },
      { href: "/users", label: "Equipe", emoji: "◔" },
    ];
  }
  return [
    ...common,
    { href: "/categories", label: "Categorias", emoji: "◇" },
    { href: "/merchants", label: "Merchants", emoji: "◍" },
    { href: "/crm", label: "CRM", emoji: "◒" },
    { href: "/business", label: "Negócio", emoji: "◧" },
    { href: "/users", label: "Usuários", emoji: "◔" },
    { href: "/settings", label: "Configuração", emoji: "▣" },
  ];
}

export function AppShell({ user, children }: { user: AuthUser; children: React.ReactNode }) {
  const pathname = usePathname();
  const links = getLinks(user.business_type);
  const branding = getBrandingForBusiness(user.business_name);
  const [theme, setTheme] = useState<ThemeMode>("light");

  useEffect(() => {
    const saved = typeof window !== 'undefined' ? (window.localStorage.getItem(THEME_KEY) as ThemeMode | null) : null;
    const preferred: ThemeMode = saved === 'dark' || saved === 'light' ? saved : 'dark';
    setTheme(preferred);
    document.documentElement.setAttribute('data-theme', preferred);
    if (typeof window !== 'undefined') window.localStorage.setItem(THEME_KEY, preferred);
  }, []);

  function toggleTheme() {
    const nextTheme: ThemeMode = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
    window.localStorage.setItem(THEME_KEY, nextTheme);
  }

  return (
    <div
      className="app-shell"
      style={{
        ["--brand-accent" as string]: branding.theme.accent,
        ["--brand-accent-strong" as string]: branding.theme.accentStrong,
        ["--brand-accent-soft" as string]: branding.theme.accentSoft,
        ["--brand-glow" as string]: branding.theme.shellGlow,
        ["--chat-outgoing" as string]: branding.theme.outgoingChat,
        ["--chat-incoming" as string]: branding.theme.incomingChat,
        ["--chat-bg" as string]: branding.theme.chatBg,
      }}
    >
      <aside className="sidebar glass-panel">
        <div className="brand-header-card">
          <div className="brand-logo-wrap">
            {branding.logoPath ? (
              <Image src={branding.logoPath} alt={branding.companyName} width={168} height={96} className="brand-logo-image" priority />
            ) : (
              <div className="brand-badge">BH</div>
            )}
          </div>
          <div>
            <div className="brand-kicker">Conta ativa</div>
            <div className="brand">{branding.appName}</div>
            <div className="brand-subtitle">{branding.subtitle}</div>
          </div>
        </div>

        <div className="sidebar-section-label">Operação</div>
        <nav className="nav-list">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className={`nav-link ${pathname === link.href ? "nav-link-active" : ""}`}>
              <span className="nav-icon">{link.emoji}</span>
              <span>{link.label}</span>
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer glass-subpanel">
          <div className="mini-kicker">Empresa</div>
          <div className="mini-title">{user.business_name}</div>
          <div className="mini-copy">{user.role} • {user.business_type}</div>
          <button className="logout-button" onClick={logout}>Sair</button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar glass-panel fade-up">
          <div>
            <div className="eyebrow">Painel administrativo premium</div>
            <h1 className="page-title">{user.business_name}</h1>
            <p className="page-subtitle">{user.name} • {user.email} • tipo: {user.business_type}</p>
          </div>
          <div className="topbar-actions">
            <button type="button" className="theme-toggle" onClick={toggleTheme}>
              {theme === "dark" ? "☀️ Modo claro" : "🌙 Modo escuro"}
            </button>
            <div className="status-chip">Sistema online</div>
            <div className="brand-token">{branding.appName}</div>
          </div>
        </header>
        <section>{children}</section>
      </main>
    </div>
  );
}
