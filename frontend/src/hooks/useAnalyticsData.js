import { useEffect, useState } from "react";

import api from "../api/client";
import { useAuth } from "../context/AuthContext";

const CACHE_TTL_MS = 5 * 60 * 1000;
const CACHE_PREFIX = "sei-bi-cache:";

function getCacheKey(endpoint, params, userId) {
  const sorted = Object.fromEntries(
    Object.entries(params).sort(([a], [b]) => a.localeCompare(b))
  );
  // Inclui o ID do usuário para isolar o cache entre usuários com permissões diferentes
  const userPart = userId != null ? `u${userId}:` : "";
  return `${CACHE_PREFIX}${userPart}${endpoint}:${JSON.stringify(sorted)}`;
}

function readCache(key) {
  try {
    const raw = sessionStorage.getItem(key);
    if (!raw) return null;
    const { data, ts } = JSON.parse(raw);
    if (Date.now() - ts > CACHE_TTL_MS) {
      sessionStorage.removeItem(key);
      return null;
    }
    return data;
  } catch {
    return null;
  }
}

function writeCache(key, data) {
  try {
    sessionStorage.setItem(key, JSON.stringify({ data, ts: Date.now() }));
  } catch {
    // sessionStorage indisponível ou cheio
  }
}

export function clearAnalyticsCache() {
  try {
    Object.keys(sessionStorage)
      .filter((k) => k.startsWith(CACHE_PREFIX))
      .forEach((k) => sessionStorage.removeItem(k));
  } catch {
    // ignore
  }
}

export function useAnalyticsData(endpoint, params, options = {}) {
  const enabled = options.enabled ?? true;
  const timeout = options.timeout;
  const { user } = useAuth();
  // Cache key inclui user.id: usuários diferentes nunca compartilham cache.
  // Quando user.id muda (troca de login), cacheKey muda e o hook re-fetcha automaticamente.
  const cacheKey = getCacheKey(endpoint, params, user?.id);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    if (!enabled) {
      setLoading(false);
      setStale(false);
      setError("");
      return () => {
        cancelled = true;
      };
    }

    const cached = readCache(cacheKey);
    if (cached) {
      setData(cached);
      setLoading(false);
      setStale(true);
      setError("");
    } else {
      setData(null);
      setLoading(true);
      setStale(false);
      setError("");
    }

    function doFetch(attempt) {
      api
        .get(endpoint, { params, timeout })
        .then((response) => {
          if (!cancelled) {
            setData(response.data);
            setStale(false);
            setLoading(false);
            writeCache(cacheKey, response.data);
          }
        })
        .catch((err) => {
          if (cancelled) return;
          // Retry automático (1×) para erros transientes (5xx, timeout, rede)
          const status = err.response?.status;
          const isRetryable = !status || status >= 500 || err.code === "ECONNABORTED";
          if (isRetryable && attempt < 1) {
            setTimeout(() => {
              if (!cancelled) doFetch(attempt + 1);
            }, 2000);
            return;
          }
          setLoading(false);
          setStale(false);
          if (!cached) {
            setError(err.response?.data?.detail || "Falha ao carregar dados.");
          }
        });
    }

    doFetch(0);

    return () => {
      cancelled = true;
    };
  }, [cacheKey, retryCount, enabled, timeout]);

  return {
    data,
    loading,
    stale,
    error,
    retry: () => setRetryCount((c) => c + 1),
  };
}
