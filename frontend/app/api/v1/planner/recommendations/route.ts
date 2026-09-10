export const runtime = "nodejs";
export const maxDuration = 200;

export async function POST(request: Request) {
  try {
    const body = await request.text();
    if (new TextEncoder().encode(body).length > 150_000) {
      return Response.json({ detail: "보고서 입력이 너무 큽니다.", retryable: false }, { status: 413 });
    }
    const response = await fetch((process.env.HEUNGMAP_BACKEND_URL ?? "http://127.0.0.1:8000") + "/api/v1/planner/recommendations", {
      method: "POST", body, headers: { "Content-Type": "application/json",
        Cookie: request.headers.get("cookie") ?? "", Origin: request.headers.get("origin") ?? "" },
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(195_000)]),
    });
    return new Response(response.body, { status: response.status, headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "application/json", "Cache-Control": "no-store",
    } });
  } catch {
    return Response.json({ detail: "보고서 서버에 연결하지 못했습니다. 규칙 보고서로 전환합니다.", retryable: true }, { status: 503 });
  }
}
