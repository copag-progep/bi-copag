import { useEffect, useState } from "react";

import api from "../api/client";

const CACHE_TTL_MS = 5 * 60 * 1000;
const CACHE_PREFIX = "sei-bi-cache:";

function getCacheKey(endpoint, params) {
  const sorted = Object.fromEntries(
    Object.entries(params).sort(([a], [b]) => a.localeCompare(b))
  );
  return `${CACHE_PREFIX}${endpoint}:${JSON.stringify(sorted)}`;
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

export function useAnalyticsData(endpoint, params) {
  const cacheKey = getCacheKey(endpoint, params);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [stale, setStale] = useState(false);
  const [error, setError] = useState("");
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

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

    api
      .get(endpoint, { params })
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
        setLoading(false);
        setStale(false);
        if (!cached) {
          setError(err.response?.data?.detail || "Falha ao carregar dados.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [cacheKey, retryCount]);

  return {
    data,
    loading,
    stale,
    error,
    retry: () => setRetryCount((c) => c + 1),
  };
}
