const PAGE_SIZE = 30;

export function normalizeUploadsPayload(payload, page = 1) {
  if (Array.isArray(payload)) {
    const total = payload.length;
    const totalPages = Math.max(Math.ceil(total / PAGE_SIZE), 1);
    const start = (page - 1) * PAGE_SIZE;
    return {
      items: payload.slice(start, start + PAGE_SIZE),
      total,
      totalPages,
    };
  }

  return {
    items: payload?.items || [],
    total: payload?.total || 0,
    totalPages: payload?.total_pages || 1,
  };
}
