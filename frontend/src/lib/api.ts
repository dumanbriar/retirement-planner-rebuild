import type { PlanInput, PlanResult } from "./types";

const BASE_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

interface ValidationItem {
  loc?: (string | number)[];
  msg?: string;
}

/** Turn a FastAPI 422 body into readable lines like "persons → 1 → current_age: …". */
function formatValidationDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationItem[])
      .map((d) => {
        const loc = (d.loc ?? []).filter((p) => p !== "body").join(" → ");
        return loc ? `${loc}: ${d.msg ?? "invalid value"}` : (d.msg ?? "invalid value");
      })
      .join("\n");
  }
  return JSON.stringify(detail);
}

async function readError(res: Response): Promise<ApiError> {
  let message = `Request failed (${res.status} ${res.statusText})`;
  try {
    const body: unknown = await res.json();
    if (body && typeof body === "object" && "detail" in body) {
      message = formatValidationDetail((body as { detail: unknown }).detail);
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, message);
}

async function post(path: string, input: PlanInput): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
  } catch {
    throw new ApiError(
      0,
      `Could not reach the planning engine at ${BASE_URL}. Is the backend running?`,
    );
  }
  if (!res.ok) throw await readError(res);
  return res;
}

export async function calculatePlan(input: PlanInput): Promise<PlanResult> {
  const res = await post("/api/plan", input);
  return (await res.json()) as PlanResult;
}

/** Download the audit workbook; every on-screen number is reproducible from it. */
export async function downloadAuditWorkbook(input: PlanInput): Promise<void> {
  const res = await post("/api/plan/excel", input);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "retirement-plan-audit.xlsx";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
