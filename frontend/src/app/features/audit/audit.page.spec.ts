import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import {
  auditFiltersFromQuery,
  auditQueryParams,
  AuditPage,
  localDatetimeInputToUtcIso,
  safeAuditJson,
  utcIsoToLocalDatetimeInput,
} from './audit.page';

class ResizeObserverStub {
  disconnect(): undefined {
    return undefined;
  }
  observe(): undefined {
    return undefined;
  }
  unobserve(): undefined {
    return undefined;
  }
}

describe('AuditPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
    await TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([{ path: 'audit', component: AuditPage }]),
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    const auth = TestBed.inject(AuthService);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'owner', display_name: null, email: null },
      roles: { is_owner: true, group_roles: {} },
    });
    auth.state.set('authenticated');
  });
  afterEach(() => http.verify());

  it('round-trips URL filters and renders newest-first API results safely', async () => {
    const router = TestBed.inject(Router);
    await router.navigateByUrl(
      '/audit?group_id=group-a&actor_id=Ada&target_id=New%20asset&action=asset.update&action=asset.archive&target_type=asset&target_type=group&created_at_from=2026-01-01T12:30:00.000Z&offset=25&limit=50',
    );
    const fixture = TestBed.createComponent(AuditPage);
    fixture.detectChanges();
    http
      .expectOne('/api/groups?archived=false&limit=100')
      .flush({ items: [{ id: 'group-a', name: 'A' }] });
    const request = http.expectOne(
      '/api/audit-events?offset=25&limit=50&group_id=group-a&actor_id=Ada&target_id=New%20asset&created_at_from=2026-01-01T12:30:00.000Z&action=asset.update&action=asset.archive&target_type=asset&target_type=group',
    );
    request.flush({
      total: 2,
      offset: 25,
      limit: 50,
      items: [
        {
          id: 'new',
          actor_id: 'actor',
          actor_name: 'Ada',
          group_id: 'group-a',
          action: 'asset.update',
          target_type: 'asset',
          target_id: 'new',
          target_name: 'New asset',
          before_state: null,
          after_state: { name: 'New' },
          correlation_id: null,
          created_at: '2026-02-01T00:00:00Z',
        },
        {
          id: 'old',
          actor_id: null,
          actor_name: null,
          group_id: 'group-a',
          action: 'asset.update',
          target_type: 'asset',
          target_id: 'old',
          target_name: null,
          before_state: null,
          after_state: null,
          correlation_id: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent.indexOf('new')).toBeLessThan(
      fixture.nativeElement.textContent.indexOf('old'),
    );
    expect(auditFiltersFromQuery(auditQueryParams(fixture.componentInstance.filters()))).toEqual(
      fixture.componentInstance.filters(),
    );
    const fromControl = fixture.nativeElement.querySelector('syn-input[type="datetime-local"]');
    expect(fromControl.value).toBe(utcIsoToLocalDatetimeInput('2026-01-01T12:30:00.000Z'));
    expect(fixture.nativeElement.querySelectorAll('syn-combobox syn-option')).toHaveLength(21);
    expect(fixture.nativeElement.textContent).toContain('Ada (actor)');
    expect(fixture.nativeElement.textContent).toContain('New asset (new)');
    expect(fixture.nativeElement.textContent).toContain('Unavailable historical entity (old)');
    expect(fixture.nativeElement.textContent).toContain('Search name or UUID.');
    expect(fixture.nativeElement.querySelector('.audit-results .events')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('.audit-results syn-pagination')).not.toBeNull();
  });

  it('accepts a single legacy audit selection and serializes multiple selections repeatedly', () => {
    expect(auditFiltersFromQuery({ action: 'asset.update', target_type: 'asset' })).toMatchObject({
      action: ['asset.update'],
      targetType: ['asset'],
    });
    expect(
      auditQueryParams({
        ...auditFiltersFromQuery({}),
        action: ['asset.update', 'asset.archive'],
        targetType: ['asset', 'group'],
      }),
    ).toMatchObject({
      action: ['asset.update', 'asset.archive'],
      target_type: ['asset', 'group'],
    });
  });

  it('round-trips browser-local datetime input through canonical UTC ISO', () => {
    const localInput = '2026-01-01T12:30';
    expect(utcIsoToLocalDatetimeInput(localDatetimeInputToUtcIso(localInput))).toBe(localInput);
  });

  it('redacts unexpected secret fields while preserving large text payloads as accessible text', () => {
    const rendered = safeAuditJson({
      password: 'nope',
      nested: { token: 'nope', value: 'x'.repeat(20_000) },
    });
    expect(rendered).toContain('[redacted]');
    expect(rendered).not.toContain('nope');
    expect(rendered).toContain('x'.repeat(20_000));
  });

  it('limits Group Admin group filters to administered groups', () => {
    const auth = TestBed.inject(AuthService);
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'admin', display_name: null, email: null },
      roles: { is_owner: false, group_roles: { managed: 'group_admin', member: 'user' } },
    });
    const fixture = TestBed.createComponent(AuditPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({
      items: [
        { id: 'managed', name: 'Managed' },
        { id: 'member', name: 'Member' },
      ],
    });
    http
      .expectOne('/api/audit-events?offset=0&limit=25')
      .flush({ items: [], total: 0, offset: 0, limit: 25 });
    expect(fixture.componentInstance.selectableGroups().map((group) => group.id)).toEqual([
      'managed',
    ]);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No audit events match');
    fixture.componentInstance.load();
    http
      .expectOne('/api/audit-events?offset=0&limit=25')
      .flush({}, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load audit history');
  });
});
