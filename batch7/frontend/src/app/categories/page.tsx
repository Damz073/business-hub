"use client";

import { useEffect, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { SimpleTable } from "@/components/SimpleTable";
import { apiFetch } from "@/lib/api";
import { CategoryResponse } from "@/types/management";

export default function CategoriesPage() {
  return <ProtectedPage>{() => <CategoriesContent />}</ProtectedPage>;
}

function CategoriesContent() {
  const [data, setData] = useState<CategoryResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<CategoryResponse>("/categories")
      .then(setData)
      .catch((err) => setError(err.message || "Erro ao carregar categorias."));
  }, []);

  return (
    <div className="card">
      <h2 className="section-title">Categorias</h2>
      {error ? <div className="error-box">{error}</div> : null}
      <SimpleTable
        headers={["Categoria", "Transações", "Merchants"]}
        rows={(data?.items || []).map((item) => [item.name, item.transactions_count, item.merchants_count])}
      />
    </div>
  );
}
