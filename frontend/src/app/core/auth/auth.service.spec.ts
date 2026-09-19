import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { provideHttpClient } from '@angular/common/http';
import { AuthService, BROWSER_LOCATION } from './auth.service';

describe('AuthService', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let assign: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    assign = vi.fn();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: BROWSER_LOCATION, useValue: { assign } },
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('stores server-resolved roles from the session response', () => {
    auth.loadSession().subscribe();
    const request = http.expectOne('/auth/session');
    expect(request.request.withCredentials).toBe(true);
    request.flush({
      authenticated: true,
      user: { id: 'user-id', display_name: 'Ada', email: 'ada@example.test' },
      roles: { is_owner: true, group_roles: { 'group-id': 'group_admin' } },
    });

    expect(auth.state()).toBe('authenticated');
    expect(auth.roles()?.is_owner).toBe(true);
  });

  it('moves to an error state when session loading fails', () => {
    auth.loadSession().subscribe();
    http
      .expectOne('/auth/session')
      .flush('unavailable', { status: 503, statusText: 'Unavailable' });

    expect(auth.state()).toBe('error');
  });

  it('clears local state and navigates only to the server-selected provider logout URL', () => {
    auth.logout().subscribe();
    const request = http.expectOne('/auth/logout');
    expect(request.request.withCredentials).toBe(true);
    request.flush({ provider_logout_url: 'https://id.example.test/realm/logout?fixed=value' });

    expect(auth.state()).toBe('anonymous');
    expect(assign).toHaveBeenCalledWith('https://id.example.test/realm/logout?fixed=value');
  });

  it('clears local state without navigating when provider logout is unavailable', () => {
    auth.logout().subscribe();
    http.expectOne('/auth/logout').flush({ provider_logout_url: null });

    expect(auth.state()).toBe('anonymous');
    expect(assign).not.toHaveBeenCalled();
  });
});
