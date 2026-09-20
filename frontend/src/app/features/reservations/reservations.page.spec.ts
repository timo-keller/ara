import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import {
  allowedReservationActions,
  localReservationTime,
  reservationFiltersFromQuery,
  reservationQueryParams,
  ReservationsPage,
} from './reservations.page';

const future = new Date(Date.now() + 60 * 60 * 1000).toISOString();
const active = {
  id: 'one',
  asset_id: 'asset',
  asset_name: 'Lab laptop',
  asset_type: 'computer',
  starts_at: future,
  ends_at: future,
  status: 'active' as const,
};

describe('ReservationsPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('only offers lifecycle actions allowed by the reservation state and time', () => {
    expect(allowedReservationActions({ ...active, status: 'returned' })).toEqual([]);
    expect(allowedReservationActions(active)).toEqual(['cancel']);
    expect(
      allowedReservationActions({
        ...active,
        starts_at: new Date(Date.now() - 1000).toISOString(),
      }),
    ).toEqual(['return']);
  });

  it('displays the API-provided asset name and an accessible unavailable fallback', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    fixture.detectChanges();
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({
      items: [active],
      total: 1,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('a')?.textContent?.trim()).toBe('Lab laptop');
    expect(fixture.nativeElement.textContent).toContain('computer');
    expect(
      fixture.nativeElement.querySelector('a[aria-label="View details for Lab laptop"]'),
    ).not.toBeNull();

    fixture.componentInstance.load();
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({
      items: [{ ...active, asset_name: null, asset_type: null }],
      total: 1,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Asset unavailable');
    expect(fixture.nativeElement.textContent).toContain('Unavailable');
    expect(fixture.nativeElement.querySelector('a')).toBeNull();
  });

  it('waits for confirmation before returning, then reloads own reservations', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    fixture.detectChanges();
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({ items: [active], total: 1 });

    fixture.componentInstance.confirm('cancel', active);
    expect(http.match('/api/reservations/one/cancel')).toHaveLength(0);
    fixture.componentInstance.performConfirmedAction();
    http.expectOne('/api/reservations/one/cancel').flush({ ...active, status: 'cancelled' });
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({ items: [], total: 0 });
    expect(fixture.componentInstance.success()).toContain('cancelled');
  });

  it('turns conflicts into schedule guidance and reloads reservations', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    fixture.detectChanges();
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({ items: [active], total: 1 });
    fixture.componentInstance.openExtension(active);
    fixture.componentInstance.extensionEnd.set(future);
    fixture.componentInstance.extend();
    http
      .expectOne('/api/reservations/one/extend')
      .flush(
        { error: { code: 'reservation_conflict', message: 'conflict' } },
        { status: 409, statusText: 'Conflict' },
      );
    http.expectOne('/api/reservations/mine?offset=0&limit=10').flush({ items: [active], total: 1 });
    expect(fixture.componentInstance.error()).toContain('current schedule');
  });

  it('renders a responsive table and sends page changes through route state', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    fixture.detectChanges();
    http
      .expectOne('/api/reservations/mine?offset=0&limit=10')
      .flush({ items: [active], total: 30 });
    fixture.detectChanges();

    expect(
      [...fixture.nativeElement.querySelectorAll('thead th')].map((header: HTMLTableCellElement) =>
        header.textContent.trim(),
      ),
    ).toEqual(['Asset name', 'Type', 'Reservation timespan', 'Actions and details']);
    expect(fixture.nativeElement.querySelector('syn-pagination')).not.toBeNull();
    fixture.componentInstance.changePage({ detail: { currentPage: 2 } } as CustomEvent);
    expect(navigate).toHaveBeenLastCalledWith([], {
      relativeTo: expect.anything(),
      queryParams: { offset: 10, limit: null },
    });
    fixture.componentInstance.changePageSize({ detail: { currentPageSize: 25 } } as CustomEvent);
    expect(navigate).toHaveBeenLastCalledWith([], {
      relativeTo: expect.anything(),
      queryParams: { offset: null, limit: 25 },
    });
  });

  it('uses local 24-hour times and restores page state from the URL', () => {
    const formatted = localReservationTime('2030-01-02T13:05:00Z');
    expect(formatted).toMatch(/\d{2}:\d{2}/);
    expect(formatted).not.toMatch(/AM|PM/);
    expect(reservationFiltersFromQuery({ offset: '25', limit: '25' })).toEqual({
      offset: 25,
      limit: 25,
    });
    expect(reservationQueryParams({ offset: 0, limit: 10 })).toEqual({ offset: null, limit: null });
  });
});
