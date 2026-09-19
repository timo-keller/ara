import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { allowedReservationActions, ReservationsPage } from './reservations.page';

const future = new Date(Date.now() + 60 * 60 * 1000).toISOString();
const active = {
  id: 'one',
  asset_id: 'asset',
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

  it('waits for confirmation before returning, then reloads own reservations', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    fixture.detectChanges();
    http.expectOne('/api/reservations/mine').flush({ items: [active] });

    fixture.componentInstance.confirm('cancel', active);
    expect(http.match('/api/reservations/one/cancel')).toHaveLength(0);
    fixture.componentInstance.performConfirmedAction();
    http.expectOne('/api/reservations/one/cancel').flush({ ...active, status: 'cancelled' });
    http.expectOne('/api/reservations/mine').flush({ items: [] });
    expect(fixture.componentInstance.success()).toContain('cancelled');
  });

  it('turns conflicts into schedule guidance and reloads reservations', () => {
    const fixture = TestBed.createComponent(ReservationsPage);
    fixture.detectChanges();
    http.expectOne('/api/reservations/mine').flush({ items: [active] });
    fixture.componentInstance.openExtension(active);
    fixture.componentInstance.extensionEnd.set(future);
    fixture.componentInstance.extend();
    http
      .expectOne('/api/reservations/one/extend')
      .flush(
        { error: { code: 'reservation_conflict', message: 'conflict' } },
        { status: 409, statusText: 'Conflict' },
      );
    http.expectOne('/api/reservations/mine').flush({ items: [active] });
    expect(fixture.componentInstance.error()).toContain('current schedule');
  });
});
