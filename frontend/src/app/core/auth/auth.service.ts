import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { catchError, map, of, tap } from 'rxjs';

export type GroupRole = 'user' | 'group_admin';

export interface SessionUser {
  id: string;
  display_name: string | null;
  email: string | null;
}

export interface EffectiveRoles {
  is_owner: boolean;
  group_roles: Record<string, GroupRole>;
}

export interface SessionResponse {
  authenticated: boolean;
  user?: SessionUser;
  roles?: EffectiveRoles;
}

export type AuthenticationState = 'loading' | 'anonymous' | 'authenticated' | 'error' | 'expired';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly session = signal<SessionResponse | null>(null);
  readonly state = signal<AuthenticationState>('loading');
  readonly user = computed(() => this.session()?.user ?? null);
  readonly roles = computed(() => this.session()?.roles ?? null);
  readonly hasGroupAccess = computed(
    () => this.roles()?.is_owner || Object.keys(this.roles()?.group_roles ?? {}).length > 0,
  );
  readonly hasAssetAdministrationAccess = computed(
    () =>
      this.roles()?.is_owner ||
      Object.values(this.roles()?.group_roles ?? {}).includes('group_admin'),
  );

  private readonly http = inject(HttpClient);

  loadSession() {
    this.state.set('loading');
    return this.http.get<SessionResponse>('/auth/session', { withCredentials: true }).pipe(
      tap((session) => this.setSession(session)),
      catchError(() => {
        this.session.set(null);
        this.state.set('error');
        return of(null);
      }),
    );
  }

  ensureSession() {
    if (this.state() !== 'loading') {
      return of(this.state() === 'authenticated');
    }
    return this.loadSession().pipe(map((session) => session?.authenticated === true));
  }

  login(): void {
    window.location.assign('/auth/login');
  }

  logout() {
    return this.http.post<void>('/auth/logout', null, { withCredentials: true }).pipe(
      tap(() => this.reset()),
      catchError(() => {
        this.reset();
        return of(undefined);
      }),
    );
  }

  expire(): void {
    this.session.set(null);
    this.state.set('expired');
  }

  reset(): void {
    this.session.set(null);
    this.state.set('anonymous');
  }

  private setSession(session: SessionResponse): void {
    if (session.authenticated && session.user && session.roles) {
      this.session.set(session);
      this.state.set('authenticated');
      return;
    }
    this.reset();
  }
}
