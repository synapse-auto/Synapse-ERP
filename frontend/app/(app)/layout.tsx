import { CascaApp } from "@/componentes/layout/CascaApp";

export default function LayoutDaAplicacao({ children }: { children: React.ReactNode }) {
  return <CascaApp>{children}</CascaApp>;
}
