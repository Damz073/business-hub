"use client";

import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { MerchantResponse } from "@/types/management";

export default function MerchantsPage() {
  return <ProtectedPage>{() => <MerchantsContent />}</ProtectedPage>;
}

function MerchantsContent() {
  const [data, setData] = useState<MerchantResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<MerchantResponse>("/merchants")
      .then(setData)
      .catch((err) => setError(err.message || "Erro ao carregar merchants."));
  }, []);

  return (
    <div className="card">
      <h2 className="section-title">Merchants aprendidos</h2>
      {error ? <div className="error-box">{error}</div> : null}
      <SimpleTable
        headers={["Nome", "Categoria padrão", "Ocorrências", "Última vez visto"]}
        rows={(data?.items || []).map((item) => [
          item.display_name,
          item.default_category || "-",
          item.occurrence_count,
          formatDateTime(item.last_seen_at),
        ])}
      />
    </div>
  );
}
