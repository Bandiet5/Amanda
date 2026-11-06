export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: { body?: unknown; csrf?: string; timeout?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(
    () => controller.abort(),
    options.timeout ?? 20000,
  );
  try {
    const response = await fetch("/api" + path, {
      method: options.body === undefined ? "GET" : "POST",
      credentials: "same-origin",
      headers: {
        ...(options.body === undefined
          ? {}
          : { "Content-Type": "application/json" }),
        ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
      },
      ...(options.body === undefined
        ? {}
        : { body: JSON.stringify(options.body) }),
      signal: controller.signal,
      cache: "no-store",
    });
    let data;
    try {
      data = await response.json();
    } catch {
      throw new ApiError(
        "We could not reach the Christmas workshop. Please check your connection.",
        "network",
        response.status,
      );
    }
    if (!response.ok)
      throw new ApiError(
        data.error ?? "Something went wrong. Please try again.",
        data.code ?? "unknown",
        response.status,
      );
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "The connection was interrupted. Let’s check your saved draw before trying again.",
      "network",
      0,
    );
  } finally {
    window.clearTimeout(timer);
  }
}
export const message = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
