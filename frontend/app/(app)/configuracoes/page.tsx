import { Suspense } from "react";
import { TelaConfiguracoes } from "@/componentes/configuracoes/TelaConfiguracoes";

export const metadata = { title: "Configurações · Synapse ERP" };

export default function PaginaConfiguracoes() {
  return (
    <Suspense>
      <TelaConfiguracoes />
    </Suspense>
  );
}
