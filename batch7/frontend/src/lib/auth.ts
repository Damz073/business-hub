import { API_URL, TOKEN_KEY } from "@/lib/config";
import { AuthUser, LoginResponse } from "@/types/auth";

export async function login(email: string, password: string) {
  const response = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload?.detail || "Falha no login.");
  }

  const data = payload as LoginResponse;
  window.localStorage.setItem(TOKEN_KEY, data.access_token);
  return data;
}

export function logout() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.location.href = "/login";
}

export function getStoredToken() {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export async function getMe(): Promise<AuthUser> {
  const token = getStoredToken();
  if (!token) {
    throw new Error("Sem token");
  }

  const response = await fetch(`${API_URL}/auth/me`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload?.detail || "Sessão inválida.");
  }

  return payload as AuthUser;
}
