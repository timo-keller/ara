import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { AdministrationPage } from './administration.page';
import { Group, RoleMapping } from './administration.service';

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

  function createReadyPage(groups: Group[] = [group], mappings: RoleMapping[] = []) {
    const fixture = TestBed.createComponent(AdministrationPage);
    fixture.detectChanges();
    http.expectOne('/api/groups?limit=100').flush({ items: groups });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: mappings });
    fixture.detectChanges();
    return fixture;
  }

  it('groups mappings by group and orders groups and mappings deterministically', () => {
    const groups: Group[] = [
      { id: 'group-z', name: 'Zulu', description: null, archived_at: null },
      { id: 'group-b', name: 'Beta', description: null, archived_at: null },
      { id: 'group-a', name: 'Alpha', description: null, archived_at: null },
    ];
    const mappings: RoleMapping[] = [
      {
        id: 'mapping-2',
        group_id: 'group-b',
        expression: 'second',
        role: 'user',
        enabled: true,
        priority: 1,
        archived_at: null,
      },
      {
        id: 'mapping-1',
        group_id: 'group-b',
        expression: 'first',
        role: 'group_admin',
        enabled: true,
        priority: 1,
        archived_at: null,
      },
      {
        id: 'mapping-3',
        group_id: 'group-b',
        expression: 'last',
        role: 'user',
        enabled: false,
        priority: 2,
        archived_at: null,
      },
      {
        id: 'mapping-4',
        group_id: 'group-a',
        expression: 'alpha',
        role: 'user',
        enabled: true,
        priority: 0,
        archived_at: null,
      },
    ];
    const fixture = createReadyPage(groups, mappings);
    const mappingGroups = Array.from(
      fixture.nativeElement.querySelectorAll('.mapping-group'),
    ) as HTMLElement[];

    expect(
      mappingGroups.map((section) => section.querySelector('h3')?.textContent?.trim()),
    ).toEqual(['Alpha', 'Beta', 'Zulu']);
    expect(
      Array.from(mappingGroups[1].querySelectorAll('code')).map((item) => item.textContent),
    ).toEqual(['first', 'second', 'last']);
    expect(mappingGroups[1].textContent).toContain('Disabled');
    expect(mappingGroups[1].querySelectorAll('syn-button').length).toBe(5);

    const betaButtons = Array.from(
      mappingGroups[1].querySelectorAll('syn-button'),
    ) as HTMLElement[];
    betaButtons[0].dispatchEvent(new Event('click'));
    expect(fixture.componentInstance.mappingDraft().id).toBe('mapping-1');
    betaButtons[1].dispatchEvent(new Event('click'));
    const disable = http.expectOne('/api/role-mappings/mapping-1/disable');
    expect(disable.request.method).toBe('POST');

    const emptyGroup = mappingGroups[2];
    expect(emptyGroup.querySelector('[role="status"]')?.textContent).toContain(
      'No role mappings have been created for this group',
    );
  });

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

  it('selects active and archived groups, resets to create mode, and preserves mapping drafts', () => {
    const archived = {
      id: 'group-2',
      name: 'Archived lab',
      description: null,
      archived_at: '2026-01-01T00:00:00Z',
    };
    const fixture = createReadyPage([group, archived]);
    const page = fixture.componentInstance;
    const listItems = fixture.nativeElement.querySelectorAll(
      '.group-list-item',
    ) as NodeListOf<HTMLElement>;
    const archivedItem = Array.from(listItems).find((item) =>
      item.textContent?.includes(archived.name),
    ) as HTMLElement;

    expect(fixture.nativeElement.textContent).toContain('Active');
    expect(fixture.nativeElement.textContent).toContain('Archived');
    archivedItem.dispatchEvent(new Event('click'));
    fixture.detectChanges();
    expect(page.groupDraft()).toEqual({ id: archived.id, name: archived.name, description: '' });
    expect(archivedItem.getAttribute('aria-current')).toBe('true');
    expect(archivedItem.getAttribute('aria-label')).toBe('Edit Archived lab, selected');

    page.changeMapping('expression', 'contains(groups, `lab`)');
    page.createGroup();
    expect(page.groupDraft()).toEqual({ id: null, name: '', description: '' });
    expect(page.mappingDraft().expression).toBe('contains(groups, `lab`)');
  });

  it('retains the selected group after group mutations and returns to create mode when it disappears', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    page.editGroup(group);
    page.changeGroup('name', 'Renamed lab');
    page.saveGroup();
    const update = http.expectOne('/api/groups/group-1');
    expect(update.request.method).toBe('PATCH');
    update.flush({ ...group, name: 'Renamed lab' });
    http.expectOne('/api/groups?limit=100').flush({ items: [{ ...group, name: 'Renamed lab' }] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    expect(page.groupDraft().id).toBe(group.id);
    expect(page.groupDraft().name).toBe('Renamed lab');

    page.archiveGroup({ ...group, name: 'Renamed lab' });
    http.expectOne('/api/groups/group-1/archive').flush({});
    http.expectOne('/api/groups?limit=100').flush({ items: [] });
    http.expectOne('/api/role-mappings?archived=false&limit=100').flush({ items: [] });
    expect(page.groupDraft()).toEqual({ id: null, name: '', description: '' });
  });

  it('explains priority and retains non-negative whole-number validation', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;
    const priorityInput = fixture.nativeElement.querySelector('syn-input[label="Priority"]');

    expect(priorityInput.getAttribute('help-text')).toBe(
      'Lower numbers are evaluated first. Equal priorities use a stable, deterministic identifier order. Priority never overrides an Owner grant.',
    );
    expect(page.mappingDraft().priority).toBe('0');

    page.changeMapping('group_id', group.id);
    page.changeMapping('expression', 'true');
    page.changeMapping('priority', '-1');
    page.saveMapping();

    expect(page.error()).toBe('Priority must be a whole number of zero or more.');

    page.changeMapping('priority', '1.5');
    page.saveMapping();

    expect(page.error()).toBe('Priority must be a whole number of zero or more.');
  });

  it('marks the optional group description without marking required mapping fields', () => {
    const fixture = createReadyPage();
    const description = fixture.nativeElement.querySelector(
      'syn-textarea[label="Description"]',
    ) as HTMLElement;

    expect(description.querySelector('[slot="help-text"] strong')?.textContent).toBe('Optional');
    for (const label of ['Group name', 'Group', 'JMESPath expression', 'Role', 'Priority']) {
      const field = fixture.nativeElement.querySelector(`[label="${label}"]`) as HTMLElement;
      expect(field.querySelector('[slot="help-text"] strong')).toBeNull();
    }
  });

  it('sends selected integer priorities when creating and editing mappings', () => {
    const fixture = createReadyPage();
    const page = fixture.componentInstance;

    page.changeMapping('group_id', group.id);
    page.changeMapping('expression', 'true');
    page.changeMapping('priority', '3');
    page.saveMapping();

    const create = http.expectOne('/api/role-mappings');
    expect(create.request.method).toBe('POST');
    expect(create.request.body.priority).toBe(3);

    page.editMapping({
      id: 'mapping-1',
      group_id: group.id,
      expression: 'true',
      role: 'user',
      enabled: true,
      priority: 3,
      archived_at: null,
    });
    page.changeMapping('priority', '4');
    page.saveMapping();

    const update = http.expectOne('/api/role-mappings/mapping-1');
    expect(update.request.method).toBe('PATCH');
    expect(update.request.body.priority).toBe(4);
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
