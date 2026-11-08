import { useCallback, useEffect, useState } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import Overview from "./sections/Overview";
import Lessons from "./sections/Lessons";
import Materials from "./sections/Materials";
import Vault from "./sections/Vault";
import Terminals from "./sections/Terminals";
import Devices from "./sections/Devices";
import AuditSection from "./sections/AuditSection";
import { loadApiState, type ApiState } from "./api";
import type { SectionId } from "./ui";

export default function App() {
  const [api, setApi] = useState<ApiState>({ kind: "checking" });
  const [section, setSection] = useState<SectionId>("overview");

  const refresh = useCallback(() => {
    setApi({ kind: "checking" });
    void loadApiState().then(setApi);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="shell">
      <Header api={api} onRefresh={refresh} />
      <div className="body">
        <Sidebar active={section} onSelect={setSection} />
        <main className="main">
          {section === "overview" && <Overview api={api} />}
          {section === "lessons" && <Lessons />}
          {section === "materials" && <Materials />}
          {section === "vault" && <Vault />}
          {section === "terminals" && <Terminals />}
          {section === "devices" && <Devices />}
          {section === "audit" && <AuditSection />}
          <footer className="footer">
            UI не является механизмом безопасности: все разрешения и состояния
            проверяются на сервере при каждом запросе. · Этап 1 — фундамент
            платформы
          </footer>
        </main>
      </div>
    </div>
  );
}
