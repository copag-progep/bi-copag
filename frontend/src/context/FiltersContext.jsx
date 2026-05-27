import { createContext, useContext, useEffect, useState } from "react";

import api from "../api/client";
import { useAuth } from "./AuthContext";

const FiltersContext = createContext(null);

const INITIAL_FILTERS = {
  data_referencia: "",
  data_inicial: "",
  data_final: "",
  setor: "",
  tipo: "",
  atribuicao: "",
};

const EMPTY_OPTIONS = {
  datas: [],
  setores: [],
  tipos: [],
  atribuicoes: [],
};

export function FiltersProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [options, setOptions] = useState(EMPTY_OPTIONS);

  async function reloadOptions({ focusLatestDate = false } = {}) {
    if (!isAuthenticated) {
      setOptions(EMPTY_OPTIONS);
      setFilters(INITIAL_FILTERS);
      return;
    }

    try {
      const { data } = await api.get("/meta/options");
      const latestDate = data.datas.at(-1) || "";

      setOptions(data);
      setFilters((current) => {
        // Se o usuário tem exatamente um setor permitido, pré-seleciona automaticamente
        // para deixar claro na UI qual recorte está sendo aplicado
        const autoSetor =
          data.setor_restrito && data.setores_do_usuario?.length === 1
            ? data.setores_do_usuario[0]
            : current.setor;
        return {
          ...current,
          data_referencia:
            focusLatestDate || !current.data_referencia
              ? latestDate
              : current.data_referencia,
          setor: autoSetor,
        };
      });
    } catch {
      setOptions(EMPTY_OPTIONS);
    }
  }

  useEffect(() => {
    reloadOptions();
  }, [isAuthenticated]);

  function setFilter(name, value) {
    setFilters((current) => ({ ...current, [name]: value }));
  }

  function clearFilters() {
    setFilters((current) => ({
      ...INITIAL_FILTERS,
      data_referencia: options.datas.at(-1) || "",
    }));
  }

  function toQueryParams() {
    return Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
  }

  return (
    <FiltersContext.Provider
      value={{
        filters,
        options,
        setFilter,
        clearFilters,
        setFilters,
        toQueryParams,
        reloadOptions,
      }}
    >
      {children}
    </FiltersContext.Provider>
  );
}

export function useFilters() {
  return useContext(FiltersContext);
}
