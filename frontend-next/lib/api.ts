const RAW_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
export const API_BASE = RAW_API_BASE.replace(/\/$/, "");

type LlmProvider = "gemini" | "openai";

type JsonRecord = Record<string, unknown>;

type VariationVariablesRequest = {
  goal: string;
  constraints: string[];
  llm: LlmProvider;
};

type VariationVariablesResponse = {
  dynamic_variables: Record<string, string[]>;
  fixed_constraints: string[];
  used_fallback?: boolean;
};

type GenerateVariationsRequest = {
  goal: string;
  dynamic_variables: Record<string, string[]>;
  constraints: string[];
  k: number;
  llm: LlmProvider;
  custom_variations?: Array<Record<string, string>>;
};

type GenerateVariationsResponse = {
  variations: Array<{ id: string } & JsonRecord>;
};

type ReferenceImagePayload = {
  data: string;
  mime_type: string;
};

type GenerateImagesResponse = {
  images: Array<{ id: string; url: string } & JsonRecord>;
};

type RunValidationRequest = {
  image_ids: string[];
  n_personas: number;
  llm: LlmProvider;
  personas?: Array<Record<string, unknown>>;
};

type RunValidationResponse = {
  evaluations: Array<JsonRecord>;
};

type SummaryResponse = JsonRecord;

type ValidationProgressResponse = {
  status: "idle" | "initializing" | "running" | "complete" | "error";
  total: number;
  completed: number;
  message?: string | null;
};

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`;
    try {
      const data = await response.json();
      if (typeof (data as { detail?: unknown }).detail === "string") {
        message = (data as { detail: string }).detail;
      } else if (typeof (data as { message?: unknown }).message === "string") {
        message = (data as { message: string }).message;
      }
    } catch {
      try {
        const text = await response.text();
        if (text) message = text;
      } catch {
        // ignore secondary errors
      }
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export async function fetchVariationVariables(
  payload: VariationVariablesRequest,
): Promise<VariationVariablesResponse> {
  return requestJson<VariationVariablesResponse>("/api/variations/variables", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateVariations(
  payload: GenerateVariationsRequest,
): Promise<GenerateVariationsResponse> {
  return requestJson<GenerateVariationsResponse>("/api/variations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function generateImages(
  variationIds: string[],
  referenceImage?: ReferenceImagePayload | null,
): Promise<GenerateImagesResponse> {
  const body: Record<string, unknown> = {
    variation_ids: variationIds,
  };
  if (referenceImage) {
    body.reference_image = referenceImage;
  }
  return requestJson<GenerateImagesResponse>("/api/images", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runValidation(
  payload: RunValidationRequest,
): Promise<RunValidationResponse> {
  return requestJson<RunValidationResponse>("/api/validate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchSummary(
  groupBy: string[],
): Promise<SummaryResponse> {
  const query = groupBy.length ? `?group_by=${encodeURIComponent(groupBy.join(","))}` : "";
  return requestJson<SummaryResponse>(`/api/summary${query}`, {
    method: "GET",
  });
}

export async function fetchValidationProgress(): Promise<ValidationProgressResponse> {
  return requestJson<ValidationProgressResponse>("/api/validate/progress", {
    method: "GET",
  });
}
