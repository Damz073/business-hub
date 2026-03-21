"use client";

import Image from "next/image";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "@/lib/auth";
import { getBrandingForBusiness } from "@/lib/branding";

export default function LoginPage() {
  const router = useRouter();
  const branding = getBrandingForBusiness("Pousada Luz do Sol");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao fazer login.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-shell">
      <div className="login-backdrop" />
      <div className="login-card premium-login-card">
        <div className="login-brand-row">
          {branding.logoPath ? (
            <div className="login-brand-logo-wrap">
              <Image src={branding.logoPath} alt={branding.companyName} width={180} height={96} className="brand-logo-image" priority />
            </div>
          ) : null}
          <div>
            <div className="eyebrow">Acesso seguro</div>
            <h1 className="login-title">{branding.companyName}</h1>
            <p className="login-subtitle">Entre com o login web criado pelo admin via WhatsApp para acessar o painel operacional.</p>
          </div>
        </div>

        {error ? <div className="error-box">{error}</div> : null}

        <form onSubmit={handleSubmit} className="form-grid">
          <label className="label">
            Email
            <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>

          <label className="label">
            Senha
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>

          <button className="button" type="submit" disabled={loading}>
            {loading ? "Entrando..." : "Entrar no painel"}
          </button>
        </form>

        <div className="helper-box">
          Backend padrão esperado em <strong>http://127.0.0.1:8000</strong>. Para mudar, crie um arquivo
          <strong> .env.local</strong> no frontend usando o modelo <strong>.env.local.example</strong>.
        </div>
      </div>
    </div>
  );
}
