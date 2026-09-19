import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { AuthService } from './auth.service';

const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function csrfToken(cookie: string): string | undefined {
  return cookie
    .split('; ')
    .find((part) => part.startsWith('ara_csrf='))
    ?.split('=')[1];
}

export function isSameOriginUrl(value: string): boolean {
  try {
    return new URL(value, window.location.origin).origin === window.location.origin;
  } catch {
    return false;
  }
}

export const csrfInterceptor: HttpInterceptorFn = (request, next) => {
  const token = csrfToken(document.cookie);
  const isSameOriginPath = isSameOriginUrl(request.url);
  const headers =
    unsafeMethods.has(request.method) && isSameOriginPath && token
      ? request.headers.set('X-CSRF-Token', decodeURIComponent(token))
      : request.headers;
  return next(
    request.clone({ headers, withCredentials: isSameOriginPath || request.withCredentials }),
  );
};

export const sessionExpiryInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  return next(request).pipe(
    catchError((error: unknown) => {
      if (
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        isSameOriginUrl(request.url)
      ) {
        auth.expire();
      }
      return throwError(() => error);
    }),
  );
};
