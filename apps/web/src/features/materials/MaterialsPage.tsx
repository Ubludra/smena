import { useState } from "react";
import { useDebounced } from "../../shared/hooks/useDebounced";
import { navigate } from "../../shared/lib/routes";
import { MaterialsList } from "./MaterialsList";

export function MaterialsPage() {
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebounced(search);

  return (
    <>
      <div className="page-header page-intro">
        <div>
          <p className="eyebrow">ВАША БИБЛИОТЕКА</p>
          <h1>Мои материалы</h1>
        </div>
        <button
          type="button"
          className="header-create page-create"
          onClick={() => navigate("#/materials/new")}
        >
          <span aria-hidden="true">＋</span>
          Создать материал
        </button>
      </div>

      <div className="search-row">
        <input
          type="search"
          className="search-input"
          placeholder="Поиск по материалам…"
          aria-label="Поиск материалов"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <MaterialsList
        search={debouncedSearch}
        onlyProtected={false}
        onEmptyAction={() => navigate("#/materials/new")}
      />
    </>
  );
}
