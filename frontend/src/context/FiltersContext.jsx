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


export function FiltersProvider({ children }) {
  const { isAuthenticated } = useAuth();
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [options, setOptions] = useState({
    datas: [],
    setores: [],
    tipos: [],
    atribuicoes: [],
  });

  useEffect(() => {
    async function loadOptions() {
      if (!isAuthenticated) {
        setOptions({ datas: [], setores: [], tipos: [], atribuicoes: [] });
        setFilters(INITIAL_FILTERS);
        return;
      }

      try {
        const { data } = await api.get("/meta/options");
        setOptions(data);
        setFilters((current) => ({
          ...current,
          data_referencia: current.data_referencia || data.datas.at(-1) || "",
        }));
      } catch {
        setOptions({ datas: [], setores: [], tipos: [], atribuicoes: [] });
      }
    }

    loadOptions();
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
      }}
    >
      {children}
    </FiltersContext.Provider>
  );
}


export function useFilters() {
  return useContext(FiltersContext);
}
