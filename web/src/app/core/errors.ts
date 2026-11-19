import { HttpErrorResponse } from '@angular/common/http';

/** Turn any error into one readable sentence for the screen. */
export function errorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    const body = err.error as { error?: { message?: string } } | null;
    if (body?.error?.message) return body.error.message;
    if (err.status === 0) return 'Cannot reach the server. Is the API running?';
  }
  return 'Something went wrong. Please try again.';
}
