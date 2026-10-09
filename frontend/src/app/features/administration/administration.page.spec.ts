import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AuthService } from '../../core/auth/auth.service';
import { AdministrationPage } from './administration.page';
import { Group, RoleMapping } from './administration.service';

const group = {
  id: 'group-1',
  name: 'Lab',
  description: 'Test lab',
  archived_at: null,
  webex_room_id: null,
};
const archived = {
  id: 'group-2',
  name: 'Archive',
  description: null,
  archived_at: '2026-01-01T00:00:00Z',
  webex_room_id: null,
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
    TestBed.inject(AuthService).loadSession().subscribe();
    http.expectOne('/auth/session').flush({
      authenticated: true,
      user: { id: 'owner', display_name: 'Owner', email: null },
      roles: { is_owner: true, group_roles: {} },
    });
  });

  afterEach(() => {
    // Existing mapping tests also select groups, which loads ancillary status.
    for (const request of http.match(
      (request) => request.method === 'GET' && request.url.endsWith('/webex'),
    )) {
      request.flush({ configured: false, counts: {}, items: [] });
    }
    http.verify();
  });

  function createReadyPage(groups: Group[] = [group], mappings: RoleMapping[] = []) {
    const fixture = TestBed.createComponent(AdministrationPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?limit=100').flush({ items: groups });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: mappings });
    fixture.detectChanges();
    return fixture;
  }

  it('allows Group Admins to manage only their groups rooms without Owner controls', () => {
    TestBed.inject(AuthService).loadSession().subscribe();
    http.expectOne('/auth/session').flush({
      authenticated: true,
      user: { id: 'admin', display_name: 'Admin', email: null },
      roles: { is_owner: false, group_roles: { [group.id]: 'group_admin', [archived.id]: 'user' } },
    });
    const fixture = TestBed.createComponent(AdministrationPage);
    http.expectOne('/api/groups?limit=100').flush({ items: [group, archived] });
    http.expectNone('/api/role-mappings?archived=false&limit=100');
    expect(fixture.componentInstance.orderedGroups()).toEqual([group]);
    fixture.componentInstance.editGroup(group);
    http
      .expectOne(`/api/groups/${group.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
    fixture.detectChanges();
    expect(
      fixture.nativeElement.querySelector('syn-input[label="Webex space link"]'),
    ).not.toBeNull();
    expect(fixture.nativeElement.querySelector('syn-input[label="Group name"]')).toBeNull();
    expect(fixture.nativeElement.querySelector('.role-mappings')).toBeNull();
    const link = 'webexteams://im?space=c149af1a-71e9-4955-a2b0-9ca8b423b129';
    expect(fixture.nativeElement.textContent).toContain('ARA Notification Bot');
    fixture.componentInstance.spaceLink.set(` ${link} `);
    fixture.componentInstance.saveWebexRoom();
    const save = http.expectOne(`/api/groups/${group.id}/webex`);
    expect(save.request.method).toBe('PATCH');
    expect(save.request.body).toEqual({ webex_space_link: link });
    save.flush({ ...group, webex_room_id: 'room-1', webex_space_link: link });
    expect(fixture.componentInstance.spaceLink()).toBe(link);
    http
      .expectOne(`/api/groups/${group.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
  });

  it('queues tests for the saved room and displays delivery status without claiming delivery', () => {
    const fixture = createReadyPage([{ ...group, webex_room_id: 'room-1' }]);
    const page = fixture.componentInstance;
    page.editGroup({ ...group, webex_room_id: 'room-1' });
    http
      .expectOne(`/api/groups/${group.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
    page.spaceLink.set('unsaved-link');
    page.testWebexRoom();
    const test = http.expectOne(`/api/groups/${group.id}/webex/test`);
    expect(test.request.method).toBe('POST');
    expect(test.request.body).toEqual({});
    test.flush({ id: 'test-1', state: 'pending' });
    http.expectOne(`/api/groups/${group.id}/webex`).flush({
      configured: true,
      counts: { pending: 1, failed: 1 },
      items: [
        {
          id: 'test-1',
          kind: 'test',
          state: 'failed',
          attempts: 1,
          created_at: '2026-01-02T10:00:00Z',
          delivered_at: null,
          error_code: 'permission_denied',
        },
      ],
    });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Test queued for the saved room');
    expect(fixture.nativeElement.textContent).toContain('permission_denied');
    expect(fixture.nativeElement.textContent).toContain('Pending: 1');
    expect(fixture.nativeElement.textContent).toContain('Failed: 1');
  });

  it('does not show stale room status after switching groups', () => {
    const fixture = createReadyPage([group, archived]);
    const page = fixture.componentInstance;
    page.editGroup(group);
    const first = http.expectOne(`/api/groups/${group.id}/webex`);
    page.editGroup(archived);
    http
      .expectOne(`/api/groups/${archived.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
    first.flush({ configured: true, counts: { failed: 10 }, items: [] });
    expect(page.webexStatus()?.counts).toEqual({});
    fixture.detectChanges();
    const input = fixture.nativeElement.querySelector('syn-input[label="Webex space link"]');
    expect(input.disabled).toBe(true);
  });

  it('retains saved settings on lookup failure and allows clearing the link', () => {
    const link = 'webexteams://im?space=c149af1a-71e9-4955-a2b0-9ca8b423b129';
    const saved = { ...group, webex_room_id: 'room-1', webex_space_link: link };
    const fixture = createReadyPage([saved]);
    const page = fixture.componentInstance;
    page.editGroup(saved);
    http
      .expectOne(`/api/groups/${group.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
    expect(page.spaceLink()).toBe(link);
    page.spaceLink.set('invalid');
    page.saveWebexRoom();
    http.expectOne(`/api/groups/${group.id}/webex`).flush(
      {
        error: { code: 'space_not_visible', message: 'Add ARA Notification Bot and try again.' },
      },
      { status: 422, statusText: 'Unprocessable Entity' },
    );
    expect(page.selectedGroup()?.webex_space_link).toBe(link);
    expect(page.webexBusy()).toBe(false);
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Add ARA Notification Bot and try again.');
    page.spaceLink.set('');
    page.saveWebexRoom();
    const clear = http.expectOne(`/api/groups/${group.id}/webex`);
    expect(clear.request.body).toEqual({ webex_space_link: null });
    clear.flush({ ...group, webex_space_link: null });
    http
      .expectOne(`/api/groups/${group.id}/webex`)
      .flush({ configured: true, counts: {}, items: [] });
    expect(page.selectedGroup()?.webex_room_id).toBeNull();
    expect(page.webexNotice()).toContain('disabled');
  });

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
