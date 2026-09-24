// Thin fetch wrapper for the Formula Manager API. Session is an httpOnly cookie;
// the custom header lets the server reject cross-site form posts.

export class ApiError extends Error {
  constructor(status, detail, errors) {
    super(detail || `Request failed (${status})`);
    this.status = status;
    this.errors = errors || (detail ? [detail] : []);
  }
}

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(method, url, body, { form } = {}) {
  const headers = { "X-Requested-With": "fm" };
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
  if (res.status === 401 && !url.startsWith("/api/auth/login")) onUnauthorized();
  if (!res.ok) {
    let data = {};
    try {
      data = await res.json();
    } catch {
      /* non-JSON error */
    }
    const detail = Array.isArray(data.detail)
      ? data.detail.map((d) => d.msg).join("; ")
      : data.detail;
    throw new ApiError(res.status, detail, data.errors);
  }
  const type = res.headers.get("content-type") || "";
  return type.includes("application/json") ? res.json() : res;
}

export const api = {
  get: (url) => request("GET", url),
  post: (url, body) => request("POST", url, body ?? {}),
  put: (url, body) => request("PUT", url, body),
  patch: (url, body) => request("PATCH", url, body),
  upload: (url, form) => request("POST", url, undefined, { form }),
};

export const qs = (params) => {
  const s = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  return s ? `?${s}` : "";
};
