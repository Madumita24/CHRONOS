import {
  certifiedChangeReviewSchema,
  type CertifiedChangeReview,
} from "@/lib/review-contract";

const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export class ReviewApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ReviewApiError";
  }
}

export class ReviewContractError extends Error {
  constructor() {
    super("The API response did not match the certified review contract.");
    this.name = "ReviewContractError";
  }
}

export async function fetchCertifiedReview(
  reviewId: string,
  options: {
    signal?: AbortSignal;
    fetcher?: typeof fetch;
    baseUrl?: string;
  } = {},
): Promise<CertifiedChangeReview> {
  const fetcher = options.fetcher ?? fetch;
  const baseUrl =
    options.baseUrl ??
    process.env.NEXT_PUBLIC_CHRONOS_API_BASE_URL ??
    DEFAULT_API_BASE_URL;
  const response = await fetcher(
    `${baseUrl}/api/reviews/${encodeURIComponent(reviewId)}`,
    {
      method: "GET",
      headers: { Accept: "application/json" },
      signal: options.signal,
      cache: "no-store",
    },
  );

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      typeof body === "object" && body !== null && "detail" in body
        ? (body as {
            detail?: { code?: unknown; message?: unknown };
          }).detail
        : undefined;
    throw new ReviewApiError(
      typeof detail?.message === "string"
        ? detail.message
        : "The certified review could not be loaded.",
      typeof detail?.code === "string" ? detail.code : "review_api_error",
      response.status,
    );
  }

  const parsed = certifiedChangeReviewSchema.safeParse(body);
  if (!parsed.success) {
    throw new ReviewContractError();
  }
  return parsed.data;
}
