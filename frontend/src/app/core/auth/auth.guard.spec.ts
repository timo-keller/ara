import { provideHttpClient } from '@angular/common/http';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { firstValueFrom } from 'rxjs';
import { routes } from '../../app.routes';
import { AuthService } from './auth.service';
import { assetAdministrationGuard, authenticatedGuard, ownerGuard } from './auth.guard';

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
});
