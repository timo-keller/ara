import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { ToastService } from '../../core/notifications/toast.service';
import {
  AssetCataloguePage,
  assetFiltersFromQuery,
  assetQueryParams,
} from './asset-catalogue.page';

describe('AssetCataloguePage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
        { provide: ToastService, useValue: { success: vi.fn(), error: vi.fn() } },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('offers only active authorized result types, accepts selections, and clears them', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    const router = TestBed.inject(Router);
    const navigate = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      total: 2,
      offset: 0,
      limit: 10,
      items: [
        {
          id: 'active',
          name: 'Active asset',
          asset_type: 'device',
          description: null,
          archived_at: null,
          availability: 'available',
        },
        {
          id: 'archived',
          name: 'Archived asset',
          asset_type: 'archived-only',
          description: null,
          archived_at: '2026-01-01',
          availability: 'reserved',
        },
        {
          id: 'reserved',
          name: 'Reserved asset',
          asset_type: 'device',
          description: null,
          archived_at: null,
          availability: 'reserved',
          reserved_by_display_name: 'Ada Lovelace',
        },
      ],
    });
    http.expectOne('/api/assets/active/reservations?limit=10').flush({ items: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Active asset');
    expect(fixture.nativeElement.textContent).toContain('Available now');
    expect(fixture.nativeElement.textContent).toContain('Reserved by Ada Lovelace');
    expect(fixture.nativeElement.textContent).not.toContain('Archived asset');
    const table = fixture.nativeElement.querySelector('table');
    expect(table).not.toBeNull();
    expect(
      [...table.querySelectorAll('thead th')].map(
        (header: HTMLTableCellElement) => header.textContent,
      ),
    ).toEqual(['Asset name', 'Asset type', 'Description', 'Availability', 'Book now', 'Details']);
    expect(
      [...table.querySelectorAll('tbody td')].map((cell: HTMLTableCellElement) =>
        cell.textContent.trim().replace(/\s+/g, ' '),
      ),
    ).toEqual([
      'Active asset',
      'device',
      'No description provided.',
      'Available now',
      '1 hour1 day1 week',
      'View details',
      'Reserved asset',
      'device',
      'No description provided.',
      'Reserved by Ada Lovelace',
      'Unavailable',
      'View details',
    ]);
    expect(table.querySelector('td[data-label="Asset name"]')?.getAttribute('headers')).toBe(
      'asset-name',
    );
    expect(table.querySelector('a[aria-label="View details for Active asset"]')).not.toBeNull();
    expect(table.querySelectorAll('syn-button')).toHaveLength(3);
    expect(
      table.querySelector('syn-button[aria-label="Book Active asset for 1 hour"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.querySelector('syn-pagination')).not.toBeNull();
    const typeFilter = fixture.nativeElement.querySelector('syn-combobox');
    expect(typeFilter.hasAttribute('restricted')).toBe(true);
    expect(typeFilter.hasAttribute('clearable')).toBe(true);
    expect(typeFilter.textContent).toContain('device');
    expect(typeFilter.textContent).not.toContain('archived-only');

    fixture.componentInstance.changeAssetType('device');
    expect(navigate).toHaveBeenLastCalledWith([], {
      relativeTo: expect.anything(),
      queryParams: assetQueryParams({
        ...fixture.componentInstance.filters(),
        assetType: 'device',
        offset: 0,
      }),
    });
    fixture.componentInstance.changeAssetType('not-an-option');
    expect(navigate).toHaveBeenCalledTimes(1);
    fixture.componentInstance.changeAssetType('');
    expect(navigate).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['1 hour', 1],
    ['1 day', 24],
    ['1 week', 168],
  ])('books an available asset for %s and refreshes availability', (label, hours) => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    const asset = {
      id: 'available',
      name: 'Available asset',
      asset_type: 'device',
      archived_at: null,
      availability: 'available',
    };
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [asset],
      total: 1,
      offset: 0,
      limit: 10,
    });
    http.expectOne('/api/assets/available/reservations?limit=10').flush({ items: [] });
    fixture.detectChanges();
    const before = Date.now();
    const button = fixture.nativeElement.querySelector(
      `syn-button[aria-label="Book Available asset for ${label}"]`,
    );
    button.dispatchEvent(new MouseEvent('click'));
    button.dispatchEvent(new MouseEvent('click'));
    const request = http.expectOne('/api/reservations');
    expect(request.request.method).toBe('POST');
    expect(request.request.body.asset_id).toBe(asset.id);
    const start = new Date(request.request.body.starts_at).getTime();
    expect(start).toBeGreaterThanOrEqual(before);
    expect(start).toBeLessThanOrEqual(Date.now());
    expect(new Date(request.request.body.ends_at).getTime() - start).toBe(
      Number(hours) * 3_600_000,
    );
    fixture.detectChanges();
    expect(
      [...fixture.nativeElement.querySelectorAll('syn-button')].every(
        (button) => (button as HTMLButtonElement).disabled,
      ),
    ).toBe(true);
    request.flush({ id: 'reservation' });
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [{ ...asset, availability: 'reserved', reserved_by_display_name: 'You' }],
      total: 1,
      offset: 0,
      limit: 10,
    });
    fixture.detectChanges();
    expect(TestBed.inject(ToastService).success).toHaveBeenCalledWith(
      `Available asset booked for ${label}.`,
    );
    expect(fixture.nativeElement.querySelector('syn-alert[variant="success"]')).toBeNull();
    expect(fixture.nativeElement.querySelectorAll('table syn-button')).toHaveLength(0);
  });

  it('explains overlapping bookings and refreshes availability after a conflict', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [{ id: 'asset', name: 'Device', archived_at: null, availability: 'available' }],
      total: 1,
      offset: 0,
      limit: 10,
    });
    http.expectOne('/api/assets/asset/reservations?limit=10').flush({ items: [] });
    fixture.detectChanges();
    fixture.nativeElement
      .querySelector('syn-button[aria-label="Book Device for 1 week"]')
      .dispatchEvent(new MouseEvent('click'));
    http
      .expectOne('/api/reservations')
      .flush({ error: { code: 'reservation_conflict' } }, { status: 409, statusText: 'Conflict' });
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [],
      total: 0,
      offset: 0,
      limit: 10,
    });
    fixture.detectChanges();
    expect(TestBed.inject(ToastService).error).toHaveBeenCalledWith(
      expect.stringContaining('another reservation overlaps this period'),
    );
    expect(fixture.componentInstance.bookingAssetId()).toBeNull();
  });

  it('keeps blocked durations visible but disabled after checking the schedule', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [{ id: 'asset', name: 'Device', archived_at: null, availability: 'available' }],
      total: 1,
      offset: 0,
      limit: 10,
    });
    fixture.detectChanges();
    const buttons = () =>
      [...fixture.nativeElement.querySelectorAll('table syn-button')] as HTMLButtonElement[];
    expect(buttons()).toHaveLength(3);
    expect(buttons().every((button) => button.disabled)).toBe(true);
    http.expectOne('/api/assets/asset/reservations?limit=10').flush({
      items: [
        {
          status: 'active',
          starts_at: new Date(Date.now() + 2 * 3_600_000).toISOString(),
          ends_at: null,
        },
      ],
    });
    fixture.detectChanges();
    expect(buttons().map((button) => button.disabled)).toEqual([false, true, true]);
    buttons()[1].dispatchEvent(new MouseEvent('click'));
    http.expectNone('/api/reservations');
  });

  it('restores legacy asset_type links and serializes page resets in the URL', () => {
    const filters = assetFiltersFromQuery({
      group_id: 'group-1',
      asset_type: 'laptop',
      availability: 'available',
      text: 'linux',
      offset: '20',
      limit: '25',
    });
    expect(filters).toEqual({
      groupId: 'group-1',
      assetType: 'laptop',
      availability: 'available',
      text: 'linux',
      offset: 20,
      limit: 25,
    });
    expect(assetQueryParams({ ...filters, assetType: '', offset: 0 })).toEqual({
      group_id: 'group-1',
      asset_type: null,
      availability: 'available',
      text: 'linux',
      offset: null,
      limit: 25,
    });
  });

  it('renders an understandable loading state', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[aria-live="polite"]')?.textContent).toContain(
      'Loading assets',
    );
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http
      .expectOne('/api/assets?offset=0&limit=10&archived=false')
      .flush({ items: [], total: 0, offset: 0, limit: 10 });
  });

  it('renders error and empty result states without catalogue results', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http
      .expectOne('/api/assets?offset=0&limit=10&archived=false')
      .flush('Unavailable', { status: 500, statusText: 'Server Error' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load assets.');

    fixture.componentInstance.load();
    http.expectOne('/api/assets?offset=0&limit=10&archived=false').flush({
      items: [],
      total: 0,
      offset: 0,
      limit: 10,
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No active assets match these filters.');
    expect(fixture.nativeElement.querySelector('table')).toBeNull();
    expect(fixture.nativeElement.querySelector('syn-pagination')).toBeNull();
  });
});
