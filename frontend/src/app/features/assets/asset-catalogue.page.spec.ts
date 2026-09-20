import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import {
  AssetCataloguePage,
  assetFiltersFromQuery,
  assetQueryParams,
} from './asset-catalogue.page';

describe('AssetCataloguePage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
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
      ],
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Active asset');
    expect(fixture.nativeElement.textContent).toContain('Available now');
    expect(fixture.nativeElement.textContent).not.toContain('Archived asset');
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
});
