import { Suspense } from "react";
import { TelaLancamentos } from "@/componentes/lancamentos/TelaLancamentos";

export const metadata = { title: "Lançamentos · Synapse ERP" };

export default function PaginaLancamentos() {
  return (
    <Suspense>
      <TelaLancamentos />
    </Suspense>
  );
}
