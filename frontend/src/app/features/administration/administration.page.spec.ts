import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AdministrationPage } from './administration.page';
import { Group, RoleMapping } from './administration.service';

const group = { id: 'group-1', name: 'Lab', description: 'Test lab', archived_at: null };
const archived = {
  id: 'group-2',
  name: 'Archive',
  description: null,
  archived_at: '2026-01-01T00:00:00Z',
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

  function createReadyPage(groups: Group[] = [group], mappings: RoleMapping[] = []) {
    const fixture = TestBed.createComponent(AdministrationPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?limit=100').flush({ items: groups });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: mappings });
    fixture.detectChanges();
    return fixture;
  }

  it('shows only the selected group mappings in priority and stable ID order', () => {
    const mappings: RoleMapping[] = [
      {
        id: 'z',
        group_id: group.id,
        expression: 'last',
        role: 'user',
        enabled: true,
        priority: 2,
        archived_at: null,
      },
      {
        id: 'b',
        group_id: group.id,
        expression: 'second',
        role: 'user',
        enabled: true,
        priority: 1,
        archived_at: null,
      },
      {
        id: 'a',
        group_id: group.id,
        expression: 'first',
        role: 'group_admin',
        enabled: false,
        priority: 1,
        archived_at: null,
      },
      {
        id: 'other',
        group_id: archived.id,
        expression: 'other group',
        role: 'user',
        enabled: true,
        priority: 0,
        archived_at: null,
      },
    ];
    const fixture = createReadyPage([group, archived], mappings);
    const page = fixture.componentInstance;
    page.editGroup(group);
    fixture.detectChanges();

    expect(fixture.nativeElement.textContent).toContain('Role mappings for Lab');
    expect(
      Array.from<Element>(fixture.nativeElement.querySelectorAll('.mapping-list code')).map(
        (item: Element) => item.textContent,
      ),
    ).toEqual(['first', 'second', 'last']);
    expect(fixture.nativeElement.textContent).not.toContain('other group');
    expect(fixture.nativeElement.querySelector('syn-select[label="Group"]')).toBeNull();
  });

  it('keeps mapping drafts and test feedback with their selected group and hides mappings in create mode', () => {
    const fixture = createReadyPage([group, archived]);
    const page = fixture.componentInstance;
    page.editGroup(group);
    page.changeMapping('expression', 'true');
    page.testMapping();
    http.expectOne('/api/role-mappings/test').flush({ matches: true });
    page.editGroup(archived);
    page.changeMapping('expression', 'false');
    page.createGroup();
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Save and select a group before managing');
    expect(
      fixture.nativeElement.querySelector('syn-textarea[label="JMESPath expression"]'),
    ).toBeNull();

    page.editGroup(group);
    expect(page.mappingDraft().expression).toBe('true');
    expect(page.testResult()).toBe(true);
    page.editGroup(archived);
    expect(page.mappingDraft().expression).toBe('false');
  });

  it('selects a newly created group before exposing its mapping controls', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.changeGroup('name', 'New group');
    page.saveGroup();
    http.expectOne('/api/groups').flush({ ...group, id: 'group-new', name: 'New group' });
    http
      .expectOne('/api/groups?limit=100')
      .flush({ items: [group, { ...group, id: 'group-new', name: 'New group' }] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    fixture.detectChanges();

    expect(page.groupDraft().id).toBe('group-new');
    expect(fixture.nativeElement.textContent).toContain('Role mappings for New group');
    expect(
      fixture.nativeElement.querySelector('syn-textarea[label="JMESPath expression"]'),
    ).not.toBeNull();
  });

  it('blocks archived mapping changes, shows its history, and restores its draft after reactivation', () => {
    const fixture = createReadyPage(
      [group, archived],
      [
        {
          id: 'mapping-1',
          group_id: archived.id,
          expression: 'archived',
          role: 'user',
          enabled: false,
          priority: 0,
          archived_at: null,
        },
      ],
    );
    const page = fixture.componentInstance;
    page.editGroup(archived);
    page.changeMapping('expression', 'staged');
    page.saveMapping();
    fixture.detectChanges();
    expect(http.match('/api/role-mappings').length).toBe(0);
    expect(fixture.nativeElement.textContent).toContain(
      'Reactivate the group before creating or changing mappings',
    );
    expect(fixture.nativeElement.textContent).toContain('archived');
    expect(fixture.nativeElement.querySelector('.mapping-list syn-button')).toBeNull();

    page.reactivateGroup(archived);
    http.expectOne('/api/groups/group-2/reactivate').flush({ ...archived, archived_at: null });
    http
      .expectOne('/api/groups?limit=100')
      .flush({ items: [group, { ...archived, archived_at: null }] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    expect(page.groupDraft().id).toBe(archived.id);
    expect(page.mappingDraft().expression).toBe('staged');
  });

  it('creates and edits mappings only in the selected group and resets that group draft after save', () => {
    const fixture = createReadyPage([group, archived]);
    const page = fixture.componentInstance;
    page.editGroup(group);
    page.changeMapping('group_id', archived.id);
    page.changeMapping('expression', 'true');
    page.changeMapping('priority', '3');
    page.saveMapping();
    const create = http.expectOne('/api/role-mappings');
    expect(create.request.body).toMatchObject({ group_id: group.id, priority: 3 });
    create.flush({});
    http.expectOne('/api/groups?limit=100').flush({ items: [group, archived] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    expect(page.mappingDraft()).toEqual({
      id: null,
      group_id: group.id,
      expression: '',
      role: 'user',
      priority: '0',
    });

    const mapping: RoleMapping = {
      id: 'mapping-1',
      group_id: group.id,
      expression: 'true',
      role: 'user',
      enabled: true,
      priority: 3,
      archived_at: null,
    };
    page.editMapping(mapping);
    page.changeMapping('priority', '4');
    page.saveMapping();
    const update = http.expectOne('/api/role-mappings/mapping-1');
    expect(update.request.body).toMatchObject({ group_id: group.id, priority: 4 });
  });

  it('retains priority validation, disable behavior, and the selected empty state', () => {
    const fixture = createReadyPage([group, archived]);
    const page = fixture.componentInstance;
    page.editGroup(group);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain(
      'No role mappings have been created for Lab',
    );
    page.changeMapping('expression', 'true');
    page.changeMapping('priority', '-1');
    page.saveMapping();
    expect(page.error()).toBe('Priority must be a whole number of zero or more.');
    const mapping: RoleMapping = {
      id: 'mapping-1',
      group_id: group.id,
      expression: 'true',
      role: 'user',
      enabled: true,
      priority: 0,
      archived_at: null,
    };
    page.disableMapping(mapping);
    const disable = http.expectOne('/api/role-mappings/mapping-1/disable');
    expect(disable.request.method).toBe('POST');
    disable.flush({});
    http.expectOne('/api/groups?limit=100').flush({ items: [group, archived] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
  });

  it('keeps group validation and archive-conflict guidance in selected-group context', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.editGroup(group);
    page.changeGroup('name', 'Changed');
    page.saveGroup();
    const update = http.expectOne('/api/groups/group-1');
    expect(update.request.method).toBe('PATCH');
    update.flush(
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

  it('keeps optional description, priority validation, and expression testing in selected-group context', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.editGroup(group);
    fixture.detectChanges();

    const description = fixture.nativeElement.querySelector(
      'syn-textarea[label="Description"]',
    ) as HTMLElement;
    expect(description.querySelector('[slot="help-text"] strong')?.textContent).toBe('Optional');
    for (const label of ['Group name', 'JMESPath expression', 'Role', 'Priority']) {
      const field = fixture.nativeElement.querySelector(`[label="${label}"]`) as HTMLElement;
      expect(field.querySelector('[slot="help-text"] strong')).toBeNull();
    }
    const priorityInput = fixture.nativeElement.querySelector('syn-input[label="Priority"]');
    expect(priorityInput.getAttribute('help-text')).toBe(
      'Lower numbers are evaluated first. Equal priorities use a stable, deterministic identifier order. Priority never overrides an Owner grant.',
    );

    page.changeMapping('expression', "contains(groups, 'ara-lab-users')");
    page.changeMapping('priority', '1.5');
    page.saveMapping();
    expect(page.error()).toBe('Priority must be a whole number of zero or more.');

    page.testMapping();
    const test = http.expectOne('/api/role-mappings/test');
    expect(test.request.method).toBe('POST');
    expect(test.request.body).toEqual({ expression: "contains(groups, 'ara-lab-users')" });
    expect(http.match('/api/role-mappings').length).toBe(0);
    test.flush({ matches: true });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('matches your current sign-in claims');
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
