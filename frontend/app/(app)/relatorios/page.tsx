import { Suspense } from "react";
import { TelaRelatorios } from "@/componentes/relatorios/TelaRelatorios";

export const metadata = { title: "Relatórios · Synapse ERP" };

export default function PaginaRelatorios() {
  return (
    <Suspense>
      <TelaRelatorios />
    </Suspense>
  );
}
