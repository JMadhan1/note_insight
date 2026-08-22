import { auth } from "../firebase";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

/** Exported so callers that need a raw fetch (streaming, multipart upload) can reuse the
 * same "get the current Firebase ID token" logic instead of duplicating it. */
export async function authHeader(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) {
    throw new ApiError(401, "Not signed in");
  }
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

/** Extracts a FastAPI error `detail` from a non-2xx response body, falling back to
 * statusText — shared by apiRequest and the raw-fetch callers below. */
async function extractErrorDetail(response: Response): Promise<string> {
  let detail = response.statusText || `Request failed with status ${response.status}`;
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      detail = data.detail;
    }
  } catch {
    // response body wasn't JSON — keep the fallback message
  }
  return detail;
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = await authHeader();

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response));
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Multipart file upload (used for the PDF/image note-transcription endpoint) —
 * apiRequest always sends JSON, so this is a small separate path rather than
 * bending apiRequest's contract to also handle FormData. */
export async function uploadFile<T>(path: string, file: File): Promise<T> {
  const headers = await authHeader();
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method: "POST", headers, body: formData });
  } catch {
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await extractErrorDetail(response));
  }
  return (await response.json()) as T;
}
