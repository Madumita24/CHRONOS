import type { z } from "zod";

import {
  analysisDetailSchema,
  analysisGraphSchema,
  analysisIndexSchema,
  evidenceListSchema,
  patchPreviewSchema,
  releaseCertificationSchema,
} from "@/lib/phase6-contract";
import type { GraphMode } from "@/lib/phase6-contract";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export class Phase6ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "Phase6ApiError";
  }
}

export class Phase6ContractError extends Error {
  constructor() {
    super("The response did not match the certified Phase 6 contract.");
    this.name = "Phase6ContractError";
  }
}

type FetchOptions = {
  signal?: AbortSignal;
  fetcher?: typeof fetch;
  baseUrl?: string;
};

async function certifiedGet<T extends z.ZodType>(
  path: string,
  schema: T,
  options: FetchOptions = {},
): Promise<z.infer<T>> {
  const baseUrl =
    options.baseUrl ??
    process.env.NEXT_PUBLIC_CHRONOS_API_BASE_URL ??
    DEFAULT_API_BASE_URL;
  const response = await (options.fetcher ?? fetch)(`${baseUrl}${path}`, {
    method: "GET",
    headers: { Accept: "application/json" },
    signal: options.signal,
    cache: "no-store",
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as { detail?: { code?: unknown; message?: unknown } }).detail
        : undefined;
    throw new Phase6ApiError(
      typeof detail?.message === "string"
        ? detail.message
        : "Certified analysis unavailable.",
      typeof detail?.code === "string" ? detail.code : "phase6_api_error",
      response.status,
    );
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new Phase6ContractError();
  return parsed.data;
}

export const fetchAnalysisIndex = (options?: FetchOptions) =>
  certifiedGet("/api/analyses", analysisIndexSchema, options);
export const fetchReleaseCertification = (options?: FetchOptions) =>
  certifiedGet("/api/phase6/release", releaseCertificationSchema, options);
export const fetchAnalysis = (analysisId: string, options?: FetchOptions) =>
  certifiedGet(
    `/api/analyses/${encodeURIComponent(analysisId)}`,
    analysisDetailSchema,
    options,
  );
export const fetchAnalysisGraph = (
  analysisId: string,
  mode: GraphMode | undefined,
  options?: FetchOptions,
) =>
  certifiedGet(
    `/api/analyses/${encodeURIComponent(analysisId)}/graph${mode ? `?mode=${encodeURIComponent(mode)}` : ""}`,
    analysisGraphSchema,
    options,
  );
export const fetchAnalysisEvidence = (
  analysisId: string,
  options?: FetchOptions,
) =>
  certifiedGet(
    `/api/analyses/${encodeURIComponent(analysisId)}/evidence`,
    evidenceListSchema,
    options,
  );
export const fetchPatchPreview = (
  analysisId: string,
  patchId: string,
  options?: FetchOptions,
) =>
  certifiedGet(
    `/api/analyses/${encodeURIComponent(analysisId)}/patches/${encodeURIComponent(patchId)}`,
    patchPreviewSchema,
    options,
  );
