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
