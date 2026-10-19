export type Issue = {
  type: string;
  day: number | null;
  period: number | null;
  section: string;
  faculty: string | null;
  room: string | null;
  message: string;
  suggestion: string;
  severity: string;
  conflicting_assignment: string | null;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public issues: Issue[] = [],
  ) {
    super(message);
  }
}
export function csrf() {
  return (
    document.cookie
      .split("; ")
      .find((v) => v.startsWith("csrftoken="))
      ?.split("=")[1] || ""
  );
}
export async function api(path: string, method = "GET", data?: unknown) {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (response.redirected)
    throw Error("Your session expired. Please sign in again.");
  const result = await response.json().catch(() => ({
    errors: response.status === 403 ? "Access denied." : "Request failed.",
  }));
  if (!response.ok)
    throw new ApiError(
      typeof result.errors === "string"
        ? result.errors
        : JSON.stringify(result.errors || result),
      result.issues || [],
    );
  return result;
}
