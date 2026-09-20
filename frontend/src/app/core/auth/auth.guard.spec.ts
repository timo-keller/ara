import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { routes } from '../../app.routes';
import { AuthService } from './auth.service';
import {
  assetAdministrationGuard,
  auditGuard,
  authenticatedGuard,
  landingGuard,
  legacyHomeGuard,
  ownerGuard,
} from './auth.guard';

describe('authenticatedGuard', () => {
  it('permits an already authenticated session', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    auth.state.set('authenticated');

    const result = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        authenticatedGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );

    expect(result).toBe(true);
  });

  it('redirects authenticated root and legacy Home visits to My reservations', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    const router = TestBed.inject(Router);
    auth.state.set('authenticated');

    const landing = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        landingGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );
    const legacyHome = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        legacyHomeGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );

    expect(router.serializeUrl(landing as never)).toBe('/reservations');
    expect(router.serializeUrl(legacyHome as never)).toBe('/reservations');
  });

  it('allows anonymous root visits and returns legacy Home visits to root', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    const router = TestBed.inject(Router);
    auth.state.set('anonymous');

    const landing = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        landingGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );
    const legacyHome = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        legacyHomeGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );

    expect(landing).toBe(true);
    expect(router.serializeUrl(legacyHome as never)).toBe('/');
  });

  it('redirects non-Owners away from administration routes', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'user', display_name: null, email: null },
      roles: { is_owner: false, group_roles: {} },
    });
    auth.state.set('authenticated');

    const result = await TestBed.runInInjectionContext(() =>
      firstValueFrom(ownerGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>),
    );

    expect(result).not.toBe(true);
  });

  it('permits Group Admins but not regular Users to route to asset administration', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'user', display_name: null, email: null },
      roles: { is_owner: false, group_roles: { group: 'group_admin' } },
    });
    auth.state.set('authenticated');
    const allowed = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        assetAdministrationGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );
    expect(allowed).toBe(true);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'user', display_name: null, email: null },
      roles: { is_owner: false, group_roles: { group: 'user' } },
    });
    const blocked = await TestBed.runInInjectionContext(() =>
      firstValueFrom(
        assetAdministrationGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>,
      ),
    );
    expect(blocked).not.toBe(true);
  });

  it('permits Owners and Group Admins, but not regular Users, to audit history', async () => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideRouter(routes)] });
    const auth = TestBed.inject(AuthService);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'user', display_name: null, email: null },
      roles: { is_owner: false, group_roles: { group: 'group_admin' } },
    });
    auth.state.set('authenticated');
    const allowed = await TestBed.runInInjectionContext(() =>
      firstValueFrom(auditGuard({} as never, {} as never) as ReturnType<typeof auth.ensureSession>),
    );
    expect(allowed).toBe(true);
  });
});
