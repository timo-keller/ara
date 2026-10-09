import { TestBed } from '@angular/core/testing';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { AssetCatalogueService, assetQuery } from './asset-catalogue.service';

describe('assetQuery', () => {
  it('maps active catalogue filters to the REST contract and excludes archived assets', () => {
    const query = assetQuery({
      groupId: 'group-1',
      assetType: 'laptop',
      availability: 'available',
      text: '  linux  ',
      offset: 10,
      limit: 25,
    });
    expect(query.toString()).toBe(
      'offset=10&limit=25&group_id=group-1&asset_type=laptop&availability=available&text=linux&archived=false',
    );
  });
});

describe('AssetCatalogueService', () => {
  let service: AssetCatalogueService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(AssetCatalogueService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads every schedule page so later conflicts are not missed', () => {
    let items: unknown[] = [];
    service.schedule('asset-1').subscribe((schedule) => {
      items = schedule.items;
    });
    const first = Array.from({ length: 10 }, (_, index) => ({ id: String(index) }));
    http.expectOne('/api/assets/asset-1/reservations?limit=10').flush({ items: first, total: 11 });
    expect(items).toEqual([]);
    http
      .expectOne('/api/assets/asset-1/reservations?limit=10&offset=10')
      .flush({ items: [{ id: 'future' }], total: 11 });
    expect(items).toEqual([...first, { id: 'future' }]);
  });

  it('requests an active-only reservation schedule for details', () => {
    service.schedule('asset-1').subscribe();
    const request = http.expectOne('/api/assets/asset-1/reservations?limit=10');
    expect(request.request.method).toBe('GET');
    request.flush({ items: [] });
  });
});
