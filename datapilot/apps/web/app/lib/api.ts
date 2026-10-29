import type { components } from "../../../../packages/api-contract";
export type User = components["schemas"]["Identity"];
export type WorkspaceInfo = components["schemas"]["Workspace"];
export type Source = components["schemas"]["DatasetSummary"];
export type ImportFile = components["schemas"]["ImportFile"];
export type ImportBatch = components["schemas"]["ImportBatch"];
export type Column = components["schemas"]["DatasetColumn"];
export type Dataset = components["schemas"]["DatasetDetail"];
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export function errorMessage(value: unknown): string { return value instanceof Error ? value.message : "Something went wrong. Please try again."; }
export function responseError(value: unknown): string {
  const body = value as { detail?: unknown };
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((d: { msg?: string }) => d.msg || "Invalid input").join(". ");
  return "The request could not be completed. Please try again.";
}
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { ...init, credentials: "same-origin", cache: "no-store", headers: { ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}), ...init.headers } });
  if (response.status === 204) return undefined as T;
  const value = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(responseError(value), response.status);
  return value as T;
}
