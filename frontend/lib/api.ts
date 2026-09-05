import type {
  AddressSearchResponse,
  PlannerAnalysisRequest,
  PlannerAnalysisResponse,
  PlannerRecommendationRequest,
  PlannerRecommendationResponse,
  Problem,
  VenueSearchResponse,
} from "./types";

const longRunningApiBase = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public problem?: Problem) {
    super(message);
  }
}

export async function analyzePlanner(request: PlannerAnalysisRequest): Promise<PlannerAnalysisResponse> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 15_000);
    let response: Response;
    try {
      response = await fetch("/api/v1/planner/analyses", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json, application/problem+json" },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
    } catch (error) {
      window.clearTimeout(timer);
      if (attempt === 0) continue;
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiError("분석 시간이 초과됐습니다. 입력은 보관되어 있으니 잠시 뒤 다시 실행해 주세요.");
      }
      throw new ApiError("분석 서버에 연결하지 못했습니다. 입력은 이 브라우저에 보관되어 있습니다.");
    }
    window.clearTimeout(timer);
    if (response.ok) return response.json() as Promise<PlannerAnalysisResponse>;
    const problem = await response.json().catch(() => ({})) as Problem;
    if (attempt === 0 && (problem.retryable || [502, 503, 504].includes(response.status))) continue;
    throw new ApiError(problem.detail || "분석 요청을 처리하지 못했습니다.", problem);
  }
  throw new ApiError("분석 요청을 처리하지 못했습니다. 입력은 이 브라우저에 보관되어 있습니다.");
}

export async function generatePlannerRecommendation(
  request: PlannerRecommendationRequest,
): Promise<PlannerRecommendationResponse> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 195_000);
  try {
    const response = await fetch(`${longRunningApiBase}/api/v1/planner/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json, application/problem+json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });
    if (response.ok) return response.json() as Promise<PlannerRecommendationResponse>;
    const problem = await response.json().catch(() => ({})) as Problem;
    throw new ApiError(problem.detail || "LLM 기획 보고서를 생성하지 못했습니다.", problem);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("LLM 보고서 생성 시간이 초과되어 규칙 보고서로 전환합니다.");
    }
    throw new ApiError("LLM 서비스에 연결하지 못해 규칙 보고서로 전환합니다.");
  } finally {
    window.clearTimeout(timer);
  }
}

async function searchRequest<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(path, {
      headers: { Accept: "application/json, application/problem+json" },
      signal: controller.signal,
    });
    if (response.ok) return response.json() as Promise<T>;
    const problem = await response.json().catch(() => ({})) as Problem;
    throw new ApiError(problem.detail || "검색 결과를 불러오지 못했습니다.", problem);
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("검색 시간이 초과됐습니다. 잠시 뒤 다시 시도하거나 직접 입력해 주세요.");
    }
    throw new ApiError("검색 서버에 연결하지 못했습니다. 직접 입력은 계속할 수 있습니다.");
  } finally {
    window.clearTimeout(timer);
  }
}

export function searchVenues(keyword: string, areaCode?: string): Promise<VenueSearchResponse> {
  const params = new URLSearchParams({ keyword, limit: "10" });
  if (areaCode) params.set("area_code", areaCode);
  return searchRequest(`/api/v1/venues/search?${params.toString()}`);
}

export function searchAddresses(query: string): Promise<AddressSearchResponse> {
  const params = new URLSearchParams({ query, limit: "10" });
  return searchRequest(`/api/v1/addresses/search?${params.toString()}`);
}
