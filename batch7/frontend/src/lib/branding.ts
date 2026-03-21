export type BrandingTheme = {
  accent: string;
  accentStrong: string;
  accentSoft: string;
  shellGlow: string;
  outgoingChat: string;
  incomingChat: string;
  chatBg: string;
};

export type BrandingConfig = {
  companyName: string;
  appName: string;
  subtitle: string;
  logoPath?: string;
  theme: BrandingTheme;
};

const defaultBranding: BrandingConfig = {
  companyName: "Business Hub",
  appName: "Business Hub",
  subtitle: "Plataforma operacional com IA",
  theme: {
    accent: "#7da4ff",
    accentStrong: "#4d7dff",
    accentSoft: "rgba(125, 164, 255, 0.18)",
    shellGlow: "rgba(125, 164, 255, 0.28)",
    outgoingChat: "#d9fdd3",
    incomingChat: "#ffffff",
    chatBg: "#efeae2",
  },
};

const luzDoSol: BrandingConfig = {
  companyName: "Pousada Luz do Sol",
  appName: "Luz do Sol",
  subtitle: "Central operacional da pousada",
  logoPath: "/brands/luz-do-sol.jpg",
  theme: {
    accent: "#b49d67",
    accentStrong: "#8f794a",
    accentSoft: "rgba(180, 157, 103, 0.17)",
    shellGlow: "rgba(180, 157, 103, 0.24)",
    outgoingChat: "#d9fdd3",
    incomingChat: "#ffffff",
    chatBg: "#efeae2",
  },
};

export function getBrandingForBusiness(businessName?: string | null): BrandingConfig {
  const normalized = (businessName || "").trim().toLowerCase();
  if (normalized.includes("luz do sol")) {
    return luzDoSol;
  }
  return defaultBranding;
}
