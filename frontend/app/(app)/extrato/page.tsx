import { Suspense } from "react";
import { TelaExtrato } from "@/componentes/extrato/TelaExtrato";

export const metadata = { title: "Extrato · Synapse ERP" };

export default function PaginaExtrato() {
  return (
    <Suspense>
      <TelaExtrato />
    </Suspense>
  );
}
