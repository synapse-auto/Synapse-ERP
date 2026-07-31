import { Suspense } from "react";
import { FormEntrar } from "@/componentes/layout/FormEntrar";

export const metadata = { title: "Entrar · Synapse ERP" };

export default function PaginaEntrar() {
  return (
    <Suspense>
      <FormEntrar />
    </Suspense>
  );
}
