"use client";
import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiFetch } from "@/lib/api";
import { ModuleManifest } from "@/types/core";

export default function BusinessPage() { return <ProtectedPage>{() => <BusinessContent />}</ProtectedPage>; }

function BusinessContent() {
  const [profile, setProfile] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { apiFetch('/core/business-profile').then(setProfile).catch((err) => setError(err.message || 'Erro ao carregar negócio.')); }, []);

  return (
    <div className="page-grid">
      {error ? <div className="error-box">{error}</div> : null}
      {!profile ? <div className="page-state">Carregando visão SaaS...</div> : (
        <>
          <div className="card hero-panel fade-up">
            <div className="hero-copy">
              <div className="eyebrow">Plataforma SaaS modular</div>
              <h2>{profile.nome}</h2>
              <p>{profile.manifest?.description}</p>
            </div>
            <div className="stat-strip">
              <div className="pill info">{profile.business_type}</div>
              <div className="pill success">Plano {profile.subscription?.plan_code || profile.plano}</div>
              <div className="pill warning">{profile.subscription?.status || 'trialing'}</div>
            </div>
          </div>

          <div className="split-grid">
            <div className="card fade-up">
              <h2 className="section-title">Módulos ativos</h2>
              <div className="module-grid">
                {(profile.enabled_modules || []).map((item: any) => (
                  <div key={item.module_key} className="module-card">
                    <div className="module-title">{item.module_key}</div>
                    <div className={`pill ${item.enabled ? "success" : "warning"}`}>{item.enabled ? 'ativo' : 'desligado'}</div>
                  </div>
                ))}
              </div>
            </div>
            <div className="card fade-up">
              <h2 className="section-title">Verticais disponíveis</h2>
              <div className="module-grid">
                {(profile.available_modules || []).map((module: ModuleManifest) => (
                  <div key={module.key} className="module-card">
                    <div className="module-title">{module.icon} {module.label}</div>
                    <div className="inline-note">{module.description}</div>
                    <div className="feature-list">{module.module_features.slice(0, 4).join(' • ')}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
