const TOKEN_STORAGE_PREFIX = "urbos.invite.";

export function rememberToken(token) {
  try {
    sessionStorage.setItem(TOKEN_STORAGE_PREFIX + "current", token);
  } catch {
    // sessionStorage unavailable (private mode etc.) — token still works
    // for this page load via the URL, just won't survive a refresh.
  }
}

export function getRememberedToken() {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE_PREFIX + "current");
  } catch {
    return null;
  }
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

export function createApiClient(token, { onUnauthorized } = {}) {
  async function request(path, options = {}) {
    const res = await fetch(`/api${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...options.headers,
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (res.status === 204) return null;

    const isJson = res.headers.get("content-type")?.includes("application/json");
    const data = isJson ? await res.json() : null;

    if (!res.ok) {
      // Covers being revoked mid-session — by someone else, or by revoking
      // your own invite from the Collaborators tab — not just the initial
      // load. Without this, further calls would just fail silently.
      if (res.status === 401) onUnauthorized?.();
      throw new ApiError(res.status, data?.error || `Request failed (${res.status})`);
    }
    return data;
  }

  return {
    getMe: () => request("/plan"),
    updatePlan: (patch) => request("/plan", { method: "PATCH", body: patch }),

    listInvites: (baseUrl) => request(`/invites?baseUrl=${encodeURIComponent(baseUrl)}`),
    createInvite: (name, role, baseUrl) =>
      request("/invites", { method: "POST", body: { name, role, baseUrl } }),
    setInviteRevoked: (id, revoked, baseUrl) =>
      request(`/invites/${id}`, { method: "PATCH", body: { revoked, baseUrl } }),

    list: (collection) => request(`/${collection}`),
    create: (collection, item) => request(`/${collection}`, { method: "POST", body: item }),
    update: (collection, id, patch) =>
      request(`/${collection}/${id}`, { method: "PATCH", body: patch }),
    remove: (collection, id) => request(`/${collection}/${id}`, { method: "DELETE" }),
  };
}

export { ApiError };
