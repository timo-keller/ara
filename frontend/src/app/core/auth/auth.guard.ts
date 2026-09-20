import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { AuthService } from './auth.service';

export const authenticatedGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(map((authenticated) => authenticated || router.createUrlTree(['/'])));
};

/** Sends authenticated visitors to their primary landing page without blocking sign-in. */
export const landingGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(map((authenticated) => (authenticated ? router.createUrlTree(['/reservations']) : true)));
};

/** Keeps existing Home bookmarks working while returning anonymous visitors to sign-in. */
export const legacyHomeGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(map((authenticated) => router.createUrlTree([authenticated ? '/reservations' : '/'])));
};

export const ownerGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(
      map((authenticated) =>
        authenticated && auth.roles()?.is_owner ? true : router.createUrlTree(['/']),
      ),
    );
};

export const groupAccessGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(
      map((authenticated) =>
        authenticated && auth.hasGroupAccess() ? true : router.createUrlTree(['/']),
      ),
    );
};

export const assetAdministrationGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth
    .ensureSession()
    .pipe(
      map((authenticated) =>
        authenticated && auth.hasAssetAdministrationAccess() ? true : router.createUrlTree(['/']),
      ),
    );
};

/** Audit queries are restricted to Owners and administrators of at least one group. */
export const auditGuard: CanActivateFn = (route, state) => assetAdministrationGuard(route, state);
