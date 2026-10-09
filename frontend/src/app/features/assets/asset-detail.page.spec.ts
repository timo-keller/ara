import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, provideRouter } from '@angular/router';
import { AssetDetailPage, localDateTimeToUtc, reservationPayload } from './asset-detail.page';

describe('asset detail quick booking', () => {
  it.each([
    ['1 hour', 1],
    ['1 day', 24],
    ['1 week', 168],
  ])('books for %s directly below the reservation heading', (label, hours) => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { paramMap: new Map([['assetId', 'asset']]) } },
        },
      ],
    });
    const http = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(AssetDetailPage);
    const asset = { id: 'asset', name: 'Device', archived_at: null };
    http.expectOne('/api/assets/asset').flush(asset);
    http.expectOne('/api/assets/asset/reservations?limit=10').flush({ items: [] });
    fixture.detectChanges();
    const heading = [...fixture.nativeElement.querySelectorAll('h2')].find(
      (element) => (element as HTMLElement).textContent === 'Reserve this asset',
    ) as HTMLElement;
    const buttons = heading.nextElementSibling!;
    expect(buttons.classList.contains('quick-booking')).toBe(true);
    expect(buttons.querySelectorAll('syn-button')).toHaveLength(3);
    fixture.componentInstance.reservations.set([
      {
        id: 'upcoming',
        asset_id: 'asset',
        asset_name: null,
        asset_type: null,
        starts_at: new Date(Date.now() + 2 * 3_600_000).toISOString(),
        ends_at: null,
        status: 'active',
        lifecycle: 'future',
      },
    ]);
    fixture.detectChanges();
    expect(
      [...buttons.querySelectorAll('syn-button')].map(
        (button) => (button as unknown as HTMLButtonElement).disabled,
      ),
    ).toEqual([false, true, true]);
    fixture.componentInstance.bookNow(24);
    http.expectNone('/api/reservations');
    fixture.componentInstance.reservations.set([]);
    fixture.detectChanges();
    const before = Date.now();
    buttons
      .querySelector(`syn-button[aria-label="Book Device for ${label}"]`)!
      .dispatchEvent(new MouseEvent('click'));
    fixture.componentInstance.bookNow(Number(hours));
    const request = http.expectOne('/api/reservations');
    const start = new Date(request.request.body.starts_at).getTime();
    expect(start).toBeGreaterThanOrEqual(before);
    expect(start).toBeLessThanOrEqual(Date.now());
    expect(request.request.body.asset_id).toBe('asset');
    expect(new Date(request.request.body.ends_at).getTime() - start).toBe(
      Number(hours) * 3_600_000,
    );
    request.flush({ id: 'reservation' });
    http.expectOne('/api/assets/asset').flush(asset);
    http.expectOne('/api/assets/asset/reservations?limit=10').flush({ items: [] });
    expect(fixture.componentInstance.reservationSuccess()).toContain('Reservation created');
    http.verify();
  });
});

describe('reservation date conversion', () => {
  it('converts a local date-time to a UTC instant', () => {
    const value = '2030-01-02T10:30';
    expect(localDateTimeToUtc(value)).toBe(new Date(value).toISOString());
  });

  it('omits ends_at for an open-ended reservation', () => {
    expect(reservationPayload('asset', '2030-01-02T10:30', '')).toEqual({
      asset_id: 'asset',
      starts_at: new Date('2030-01-02T10:30').toISOString(),
    });
  });
});
