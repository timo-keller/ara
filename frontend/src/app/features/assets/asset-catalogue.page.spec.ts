import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AssetCataloguePage } from './asset-catalogue.page';

describe('AssetCataloguePage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('keeps archived data out of the rendered catalogue and maps page changes', () => {
    const fixture = TestBed.createComponent(AssetCataloguePage);
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
          asset_type: 'device',
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

    fixture.componentInstance.changePage(new CustomEvent('page', { detail: { currentPage: 2 } }));
    const page = http.expectOne('/api/assets?offset=10&limit=10&archived=false');
    expect(page.request.method).toBe('GET');
    page.flush({ items: [], total: 0, offset: 10, limit: 10 });
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
