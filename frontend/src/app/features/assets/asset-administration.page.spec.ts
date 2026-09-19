import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { AssetAdministrationPage } from './asset-administration.page';

const groups = [
  { id: 'group-admin', name: 'Admin group' },
  { id: 'group-user', name: 'User group' },
  { id: 'group-other', name: 'Other group' },
];
const activeAsset = {
  id: 'asset-active',
  group_id: 'group-admin',
  asset_type: 'laptop',
  name: 'Build laptop',
  description: null,
  operational_metadata: null,
  remote_host: null,
  remote_url: null,
  operating_system: null,
  access_instructions: null,
  webex_room_id: null,
  archived_at: null,
};

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

describe('AssetAdministrationPage', () => {
  let http: HttpTestingController;
  let auth: AuthService;

  beforeEach(async () => {
    globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
    await TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
  });

  afterEach(() => http.verify());

  function setRoles(is_owner: boolean, group_roles: Record<string, 'user' | 'group_admin'>): void {
    (auth as unknown as { session: { set(value: unknown): void } }).session.set({
      authenticated: true,
      user: { id: 'user', display_name: null, email: null },
      roles: { is_owner, group_roles },
    });
    auth.state.set('authenticated');
  }

  function createReadyPage() {
    const fixture = TestBed.createComponent(AssetAdministrationPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: groups });
    http.expectOne('/api/assets?archived=false&limit=100').flush({
      items: [{ ...activeAsset, group_id: 'group-user', name: 'User group laptop' }, activeAsset],
    });
    http.expectOne('/api/assets?archived=true&limit=100').flush({
      items: [
        { ...activeAsset, id: 'asset-archived', name: 'Old laptop', archived_at: '2026-01-01' },
      ],
    });
    fixture.detectChanges();
    return fixture;
  }

  it('limits Group Admin group selection and makes archive state visible', () => {
    setRoles(false, { 'group-admin': 'group_admin', 'group-user': 'user' });
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    expect(page.manageableGroups().map((group) => group.id)).toEqual(['group-admin']);
    expect(page.manageableAssets().map((asset) => asset.group_id)).toEqual([
      'group-admin',
      'group-admin',
    ]);
    expect(fixture.nativeElement.textContent).not.toContain('User group laptop');
    expect(fixture.nativeElement.textContent).toContain('Archived');
    expect(fixture.nativeElement.querySelectorAll('syn-input[type="password"]')).toHaveLength(0);
  });

  it('allows Owners to select every active group', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    expect(fixture.componentInstance.manageableGroups().map((group) => group.id)).toEqual(
      groups.map((group) => group.id),
    );
  });

  it('creates, edits, archives, and reactivates using the asset API contract', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.changeGroup('group-admin');
    page.change('name', 'New laptop');
    page.change('asset_type', 'laptop');
    page.change('remote_host', 'remote.example.test');
    page.change('webex_room_id', 'room-42');
    page.change('operational_metadata_text', '{"location":"Lab A"}');
    page.save();
    const create = http.expectOne('/api/assets');
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual({
      group_id: 'group-admin',
      asset_type: 'laptop',
      name: 'New laptop',
      description: null,
      operational_metadata: { location: 'Lab A' },
      remote_host: 'remote.example.test',
      remote_url: null,
      operating_system: null,
      access_instructions: null,
      webex_room_id: 'room-42',
    });
    create.flush(activeAsset);
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: groups });
    http.expectOne('/api/assets?archived=false&limit=100').flush({ items: [activeAsset] });
    http.expectOne('/api/assets?archived=true&limit=100').flush({ items: [] });

    page.edit(activeAsset);
    page.change('name', 'Updated laptop');
    page.save();
    const update = http.expectOne('/api/assets/asset-active');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body.group_id).toBeUndefined();
    expect(update.request.body.name).toBe('Updated laptop');
    update.flush(activeAsset);
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: groups });
    http.expectOne('/api/assets?archived=false&limit=100').flush({ items: [activeAsset] });
    http.expectOne('/api/assets?archived=true&limit=100').flush({ items: [] });

    page.archive(activeAsset);
    const archive = http.expectOne('/api/assets/asset-active/archive');
    expect(archive.request.method).toBe('POST');
    archive.flush(activeAsset);
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: groups });
    http.expectOne('/api/assets?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?archived=true&limit=100').flush({ items: [activeAsset] });

    page.reactivate(activeAsset);
    const reactivate = http.expectOne('/api/assets/asset-active/reactivate');
    expect(reactivate.request.method).toBe('POST');
    reactivate.flush(activeAsset);
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: groups });
    http.expectOne('/api/assets?archived=false&limit=100').flush({ items: [activeAsset] });
    http.expectOne('/api/assets?archived=true&limit=100').flush({ items: [] });
  });

  it('renders loading, empty, and error states', () => {
    setRoles(true, {});
    const fixture = TestBed.createComponent(AssetAdministrationPage);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Loading assets');
    http.expectOne('/api/groups?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?archived=false&limit=100').flush({ items: [] });
    http.expectOne('/api/assets?archived=true&limit=100').flush({ items: [] });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No assets are available to administer');
    fixture.componentInstance.load();
    http
      .expectOne('/api/groups?archived=false&limit=100')
      .flush({}, { status: 500, statusText: 'Error' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('We could not load assets');
  });
});
