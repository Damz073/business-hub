"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getMe } from "@/lib/auth";
import { AuthUser } from "@/types/auth";
import { AppShell } from "@/components/AppShell";

export function ProtectedPage({ children }: { children: (user: AuthUser) => React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    getMe()
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message || "Sessão inválida.");
        setTimeout(() => router.push("/login"), 800);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [router]);

  if (loading) {
    return <div className="page-state">Carregando dashboard...</div>;
  }

  if (error || !user) {
    return <div className="page-state">{error || "Usuário não encontrado."}</div>;
  }

  return <AppShell user={user}>{children(user)}</AppShell>;
}
