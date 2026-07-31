import { Suspense } from "react";
import { TelaDashboard } from "@/componentes/dashboard/TelaDashboard";

export const metadata = { title: "Dashboard · Synapse ERP" };

export default function PaginaDashboard() {
  return (
    <Suspense>
      <TelaDashboard />
    </Suspense>
  );
}
