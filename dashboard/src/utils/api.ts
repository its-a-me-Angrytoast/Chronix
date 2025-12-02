export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Handle unauthorized globally if needed, e.g. redirect
      // window.location.href = '/api/auth/login'; // Optional: auto-redirect
    }
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(errorData.error || errorData.message || 'An error occurred', response.status);
  }

  return response.json();
}
