import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AdministrationPage } from './administration.page';

const group = { id: 'group-1', name: 'Lab', description: 'Test lab', archived_at: null };

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

describe('AdministrationPage', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
    await TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  function createReadyPage() {
    const fixture = TestBed.createComponent(AdministrationPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?limit=100').flush({ items: [group] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    fixture.detectChanges();
    return fixture;
  }

  it('creates groups and sends mapping tests only to the non-persisting test endpoint', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.changeGroup('name', 'New group');
    page.saveGroup();
    const create = http.expectOne('/api/groups');
    expect(create.request.method).toBe('POST');
    create.flush({ ...group, id: 'group-2', name: 'New group' });
    http.expectOne('/api/groups?limit=100').flush({ items: [group] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });

    page.changeMapping('expression', "contains(groups, 'ara-lab-users')");
    page.testMapping();
    const test = http.expectOne('/api/role-mappings/test');
    expect(test.request.method).toBe('POST');
    expect(test.request.body).toEqual({ expression: "contains(groups, 'ara-lab-users')" });
    test.flush({ matches: true });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('matches your current sign-in claims');
  });

  it('presents API validation details and unresolved reservation resolution steps', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.changeGroup('name', 'Changed');
    page.saveGroup();
    http
      .expectOne('/api/groups')
      .flush(
        { error: { message: 'Request validation failed', details: [{ message: 'Too long' }] } },
        { status: 422, statusText: 'Invalid' },
      );
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Too long');

    page.archiveGroup(group);
    http.expectOne('/api/groups/group-1/archive').flush(
      {
        error: {
          code: 'group_has_unresolved_reservations',
          message: 'Group has unresolved reservations',
          details: [
            {
              reservation_id: 'reservation-1',
              asset_id: 'asset-1',
              resolution: 'Return or cancel this reservation before archiving.',
            },
          ],
        },
      },
      { status: 409, statusText: 'Conflict' },
    );
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('reservation-1');
    expect(fixture.nativeElement.textContent).toContain('Return or cancel');
  });

  it('renders loading, empty, and load error states', () => {
    const fixture = TestBed.createComponent(AdministrationPage);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Loading administration data');
    http.expectOne('/api/groups?limit=100').flush({ items: [] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No groups have been created');

    fixture.componentInstance.load();
    http.expectOne('/api/groups?limit=100').flush({}, { status: 500, statusText: 'Server error' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load administration data');
  });
});
