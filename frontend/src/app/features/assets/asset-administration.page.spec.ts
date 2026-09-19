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

  it('marks optional asset fields in help text without marking required fields', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    const optionalLabels = [
      'Description',
      'Remote host',
      'Remote URL',
      'Operating system',
      'Access instructions',
      'Operational metadata (JSON)',
      'Webex room identifier',
    ];

    for (const label of optionalLabels) {
      const field = fixture.nativeElement.querySelector(`[label="${label}"]`) as HTMLElement;
      expect(field.querySelector('[slot="help-text"] strong')?.textContent).toBe('Optional');
    }
    expect(
      fixture.nativeElement.querySelector('[label="Remote host"] [slot="help-text"]')?.textContent,
    ).toContain('no credentials');
    for (const label of ['Group', 'Asset name', 'Asset type']) {
      const field = fixture.nativeElement.querySelector(`[label="${label}"]`) as HTMLElement;
      expect(field.querySelector('[slot="help-text"] strong')).toBeNull();
    }
  });

  it('selects an asset from the keyboard-accessible list and returns to a blank draft', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    const assetButton = fixture.nativeElement.querySelector(
      'button[aria-label="Edit Build laptop"]',
    ) as HTMLButtonElement;

    expect(assetButton).not.toBeNull();
    assetButton.click();
    fixture.detectChanges();
    expect(page.draft().id).toBe('asset-active');
    expect(page.draft().name).toBe('Build laptop');
    expect(assetButton.getAttribute('aria-current')).toBe('true');
    expect(fixture.nativeElement.textContent).toContain('Editing Build laptop');

    page.createAsset();
    fixture.detectChanges();
    expect(page.draft().id).toBeNull();
    expect(fixture.nativeElement.querySelector('[aria-current="true"]')).toBeNull();
  });

  it('suggests normalized asset types only from the selected manageable group', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.assets.set([
      { ...activeAsset, asset_type: ' Laptop ' },
      { ...activeAsset, id: 'asset-duplicate', asset_type: 'laptop' },
      {
        ...activeAsset,
        id: 'asset-archived-type',
        asset_type: 'Test   bench',
        archived_at: '2026-01-01',
      },
      { ...activeAsset, id: 'asset-user', group_id: 'group-user', asset_type: 'Camera' },
      { ...activeAsset, id: 'asset-other', group_id: 'group-other', asset_type: 'Server' },
    ]);

    page.changeGroup('group-admin');
    expect(page.assetTypeSuggestions()).toEqual(['Laptop', 'Test bench']);
    page.changeGroup('group-user');
    expect(page.assetTypeSuggestions()).toEqual(['Camera']);
    page.changeGroup('group-other');
    expect(page.assetTypeSuggestions()).toEqual(['Server']);
  });

  it('limits suggestions to a Group Admin scope and uses an edited asset group', () => {
    setRoles(false, { 'group-admin': 'group_admin', 'group-user': 'user' });
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.assets.set([
      { ...activeAsset, asset_type: 'Laptop' },
      {
        ...activeAsset,
        id: 'asset-archived-type',
        asset_type: 'Test bench',
        archived_at: '2026-01-01',
      },
      { ...activeAsset, id: 'asset-user', group_id: 'group-user', asset_type: 'Camera' },
    ]);

    page.changeGroup('group-user');
    expect(page.assetTypeSuggestions()).toEqual([]);
    page.edit({ ...activeAsset, asset_type: 'Laptop' });
    expect(page.assetTypeSuggestions()).toEqual(['Laptop', 'Test bench']);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('syn-combobox')).not.toBeNull();
  });

  it('suggests unique non-empty Webex room identifiers for the selected manageable group', () => {
    setRoles(false, { 'group-admin': 'group_admin', 'group-user': 'user' });
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.assets.set([
      { ...activeAsset, webex_room_id: ' room-admin ' },
      { ...activeAsset, id: 'asset-duplicate', webex_room_id: 'room-admin' },
      {
        ...activeAsset,
        id: 'asset-archived-room',
        archived_at: '2026-01-01',
        webex_room_id: 'room-archived',
      },
      { ...activeAsset, id: 'asset-empty', webex_room_id: '  ' },
      { ...activeAsset, id: 'asset-null', webex_room_id: null },
      { ...activeAsset, id: 'asset-user', group_id: 'group-user', webex_room_id: 'room-user' },
    ]);

    page.changeGroup('group-admin');
    expect(page.webexRoomIdSuggestions()).toEqual(['room-admin', 'room-archived']);
    page.changeGroup('group-user');
    expect(page.webexRoomIdSuggestions()).toEqual([]);
    page.edit({ ...activeAsset, webex_room_id: 'room-admin' });
    expect(page.webexRoomIdSuggestions()).toEqual(['room-admin', 'room-archived']);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelectorAll('syn-combobox syn-option')).toHaveLength(3);
  });

  it('creates, edits, archives, and reactivates using the asset API contract', () => {
    setRoles(true, {});
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.changeGroup('group-admin');
    page.change('name', 'New laptop');
    page.changeAssetType('New custom type');
    page.change('remote_host', 'remote.example.test');
    page.changeWebexRoomId('room-42');
    page.change('operational_metadata_text', '{"location":"Lab A"}');
    page.save();
    const create = http.expectOne('/api/assets');
    expect(create.request.method).toBe('POST');
    expect(create.request.body).toEqual({
      group_id: 'group-admin',
      asset_type: 'New custom type',
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
    expect(page.draft().id).toBe('asset-active');

    page.edit(activeAsset);
    page.change('name', 'Updated laptop');
    page.changeWebexRoomId('  ');
    page.save();
    const update = http.expectOne('/api/assets/asset-active');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body.group_id).toBeUndefined();
    expect(update.request.body.name).toBe('Updated laptop');
    expect(update.request.body.webex_room_id).toBeNull();
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
    http.expectOne('/api/assets?archived=true&limit=100').flush({
      items: [{ ...activeAsset, archived_at: '2026-01-01' }],
    });
    expect(page.draft().id).toBe('asset-active');
    expect(page.draft().archived_at).toBe('2026-01-01');

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
