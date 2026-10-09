import { HttpErrorResponse } from '@angular/common/http';
import { DatePipe } from '@angular/common';
import { of } from 'rxjs';
import { AuthService } from '../../core/auth/auth.service';
import { ToastService } from '../../core/notifications/toast.service';
import { Component, computed, inject, signal } from '@angular/core';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynBadgeComponent } from '@synergy-design-system/angular/components/badge';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynOptionComponent } from '@synergy-design-system/angular/components/option';
import { SynSelectComponent } from '@synergy-design-system/angular/components/select';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { SynTextareaComponent } from '@synergy-design-system/angular/components/textarea';
import {
  AdministrationService,
  ApiError,
  ApiErrorDetail,
  Group,
  RoleMapping,
  WebexStatus,
} from './administration.service';

interface GroupDraft {
  id: string | null;
  name: string;
  description: string;
}

interface MappingDraft {
  id: string | null;
  group_id: string;
  expression: string;
  role: 'user' | 'group_admin';
  priority: string;
}

const emptyGroupDraft = (): GroupDraft => ({ id: null, name: '', description: '' });

const emptyMappingDraft = (groupId = ''): MappingDraft => ({
  id: null,
  group_id: groupId,
  expression: '',
  role: 'user',
  priority: '0',
});

@Component({
  imports: [
    SynAlertComponent,
    SynBadgeComponent,
    SynButtonComponent,
    SynCardComponent,
    SynInputComponent,
    SynOptionComponent,
    SynSelectComponent,
    SynSpinnerComponent,
    SynTextareaComponent,
    DatePipe,
  ],
  selector: 'app-administration-page',
  styleUrl: './administration.page.scss',
  templateUrl: './administration.page.html',
})
export class AdministrationPage {
  private readonly administration = inject(AdministrationService);
  private readonly auth = inject(AuthService);
  private readonly toast = inject(ToastService);
  readonly isOwner = computed(() => !!this.auth.roles()?.is_owner);
  readonly spaceLink = signal('');
  readonly webexStatus = signal<WebexStatus | null>(null);
  readonly webexState = signal<'loading' | 'ready' | 'error'>('ready');
  readonly webexNotice = signal<string | null>(null);
  readonly webexBusy = signal(false);
  readonly groups = signal<Group[]>([]);
  readonly orderedGroups = computed(() =>
    [...this.groups()].sort((left, right) => this.compareByNameAndId(left, right)),
  );
  readonly selectedGroup = computed(
    () => this.groups().find((group) => group.id === this.groupDraft().id) ?? null,
  );
  readonly mappings = signal<RoleMapping[]>([]);
  readonly selectedMappings = computed(() => {
    const selectedGroup = this.selectedGroup();
    if (!selectedGroup) return [];
    return this.mappings()
      .filter((mapping) => mapping.group_id === selectedGroup.id && !mapping.archived_at)
      .sort((left, right) =>
        left.priority === right.priority
          ? this.compareStrings(left.id, right.id)
          : left.priority - right.priority,
      );
  });
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly archiveConflicts = signal<ApiErrorDetail[]>([]);
  readonly groupDraft = signal<GroupDraft>(emptyGroupDraft());
  private readonly mappingDrafts = signal<Record<string, MappingDraft>>({});
  private readonly mappingTestResults = signal<Record<string, boolean | null>>({});
  readonly mappingDraft = computed(() => {
    const selectedGroup = this.selectedGroup();
    return selectedGroup
      ? (this.mappingDrafts()[selectedGroup.id] ?? emptyMappingDraft(selectedGroup.id))
      : emptyMappingDraft();
  });
  readonly testResult = computed(() => {
    const selectedGroup = this.selectedGroup();
    return selectedGroup ? (this.mappingTestResults()[selectedGroup.id] ?? null) : null;
  });

  constructor() {
    this.load();
  }

  load(selectedGroupId: string | null = this.groupDraft().id): void {
    this.state.set('loading');
    this.administration.groups().subscribe({
      next: ({ items }) => {
        items = this.isOwner()
          ? items
          : items.filter((group) => this.auth.roles()?.group_roles[group.id] === 'group_admin');
        this.groups.set(items);
        const mappingsRequest = this.isOwner() ? this.administration.mappings() : of({ items: [] });
        mappingsRequest.subscribe({
          next: ({ items: mappings }) => {
            this.mappings.set(mappings);
            if (selectedGroupId) {
              const selected = items.find((group) => group.id === selectedGroupId);
              if (selected) this.editGroup(selected);
              else this.createGroup();
            }
            this.state.set('ready');
          },
          error: (error) => this.loadError(error),
        });
      },
      error: (error) => this.loadError(error),
    });
  }

  changeGroup(field: 'name' | 'description', value: string): void {
    this.groupDraft.update((draft) => ({ ...draft, [field]: value }));
  }

  editGroup(group: Group): void {
    this.groupDraft.set({ id: group.id, name: group.name, description: group.description ?? '' });
    this.ensureMappingContext(group.id);
    this.spaceLink.set(group.webex_space_link ?? '');
    this.webexNotice.set(null);
    this.webexBusy.set(false);
    this.refreshWebex();
  }

  createGroup(): void {
    this.archiveConflicts.set([]);
    this.groupDraft.set(emptyGroupDraft());
    this.webexStatus.set(null);
  }

  saveGroup(): void {
    const draft = this.groupDraft();
    if (!draft.name.trim()) return this.showError('A group name is required.');
    const payload = { name: draft.name.trim(), description: draft.description || null };
    const request = draft.id
      ? this.administration.updateGroup(draft.id, payload)
      : this.administration.createGroup(payload);
    request.subscribe({
      next: (group) => this.load(group.id),
      error: (error) => this.showApiError(error),
    });
  }

  refreshWebex(): void {
    const id = this.groupDraft().id;
    if (!id) return;
    this.webexStatus.set(null);
    this.webexState.set('loading');
    this.administration.webexStatus(id).subscribe({
      next: (status) => {
        if (this.groupDraft().id !== id) return;
        this.webexStatus.set(status);
        this.webexState.set('ready');
      },
      error: (error) => {
        if (this.groupDraft().id !== id) return;
        this.webexState.set('error');
        this.showApiError(error, 'Could not load delivery status. Try refreshing.');
      },
    });
  }

  saveWebexRoom(): void {
    const id = this.groupDraft().id;
    if (!id || this.webexBusy()) return;
    this.webexBusy.set(true);
    this.webexNotice.set('Resolving and saving Webex space…');
    this.administration.updateWebexRoom(id, this.spaceLink().trim() || null).subscribe({
      next: (group) => {
        this.groups.update((groups) => groups.map((item) => (item.id === group.id ? group : item)));
        if (this.groupDraft().id !== id) return;
        this.webexBusy.set(false);
        this.spaceLink.set(group.webex_space_link ?? '');
        this.webexNotice.set(
          group.webex_room_id
            ? 'Webex space saved. Send a test message to verify delivery.'
            : 'Room notifications disabled.',
        );
        this.refreshWebex();
      },
      error: (error) => {
        if (this.groupDraft().id !== id) return;
        this.webexBusy.set(false);
        this.webexNotice.set(null);
        this.showApiError(error);
      },
    });
  }

  testWebexRoom(): void {
    const id = this.groupDraft().id;
    if (!id || this.webexBusy()) return;
    this.webexBusy.set(true);
    this.administration.testWebexRoom(id).subscribe({
      next: () => {
        if (this.groupDraft().id !== id) return;
        this.webexBusy.set(false);
        this.webexNotice.set(
          'Test queued for the saved room. Refresh status shortly to see the result.',
        );
        this.refreshWebex();
      },
      error: (error) => {
        if (this.groupDraft().id !== id) return;
        this.webexBusy.set(false);
        this.showApiError(error);
      },
    });
  }

  archiveGroup(group: Group): void {
    this.archiveConflicts.set([]);
    this.administration.archiveGroup(group.id).subscribe({
      next: () => this.load(group.id),
      error: (error) => {
        const details = this.apiError(error)?.error?.details ?? [];
        if (this.apiError(error)?.error?.code === 'group_has_unresolved_reservations') {
          this.archiveConflicts.set(details);
        }
        this.showApiError(error);
      },
    });
  }

  reactivateGroup(group: Group): void {
    this.administration
      .reactivateGroup(group.id)
      .subscribe({ next: () => this.load(group.id), error: (e) => this.showApiError(e) });
  }

  changeMapping(
    field: keyof Omit<MappingDraft, 'id'>,
    value: string | number | (string | number)[],
  ): void {
    const selectedGroup = this.selectedGroup();
    if (!selectedGroup) return;
    this.mappingDrafts.update((drafts) => ({
      ...drafts,
      [selectedGroup.id]: {
        ...this.mappingDraft(),
        [field]: field === 'group_id' ? selectedGroup.id : String(value),
      },
    }));
  }

  editMapping(mapping: RoleMapping): void {
    const group = this.groups().find((candidate) => candidate.id === mapping.group_id);
    if (!group) return;
    this.editGroup(group);
    this.mappingDrafts.update((drafts) => ({
      ...drafts,
      [group.id]: {
        id: mapping.id,
        group_id: mapping.group_id,
        expression: mapping.expression,
        role: mapping.role,
        priority: String(mapping.priority),
      },
    }));
  }

  saveMapping(): void {
    const selectedGroup = this.selectedGroup();
    const draft = this.mappingDraft();
    if (!selectedGroup || selectedGroup.archived_at) return;
    if (!draft.expression.trim()) return this.showError('Enter an expression.');
    const priority = Number(draft.priority);
    if (!Number.isInteger(priority) || priority < 0)
      return this.showError('Priority must be a whole number of zero or more.');
    const payload = {
      group_id: selectedGroup.id,
      expression: draft.expression.trim(),
      role: draft.role,
      priority,
      enabled: true,
    };
    const request = draft.id
      ? this.administration.updateMapping(draft.id, payload)
      : this.administration.createMapping(payload);
    request.subscribe({
      next: () => this.resetMappingAndLoad(selectedGroup.id),
      error: (error) => this.showApiError(error),
    });
  }

  disableMapping(mapping: RoleMapping): void {
    this.administration
      .disableMapping(mapping.id)
      .subscribe({ next: () => this.load(mapping.group_id), error: (e) => this.showApiError(e) });
  }

  testMapping(): void {
    const selectedGroup = this.selectedGroup();
    if (!selectedGroup) return;
    this.mappingTestResults.update((results) => ({ ...results, [selectedGroup.id]: null }));
    const expression = this.mappingDraft().expression.trim();
    if (!expression) return this.showError('Enter an expression to test.');
    this.administration.testExpression(expression).subscribe({
      next: ({ matches }) =>
        this.mappingTestResults.update((results) => ({ ...results, [selectedGroup.id]: matches })),
      error: (error) => this.showApiError(error),
    });
  }

  private resetMappingAndLoad(groupId: string): void {
    this.mappingDrafts.update((drafts) => ({ ...drafts, [groupId]: emptyMappingDraft(groupId) }));
    this.mappingTestResults.update((results) => ({ ...results, [groupId]: null }));
    this.load(groupId);
  }

  private ensureMappingContext(groupId: string): void {
    if (this.mappingDrafts()[groupId]) return;
    this.mappingDrafts.update((drafts) => ({ ...drafts, [groupId]: emptyMappingDraft(groupId) }));
  }

  private loadError(error: unknown): void {
    this.state.set('error');
    this.showApiError(error);
  }

  private showApiError(error: unknown, fallback = 'The request could not be completed.'): void {
    const apiError = this.apiError(error)?.error;
    const validation = apiError?.details
      ?.map((detail) => detail.message)
      .filter(Boolean)
      .join(' ');
    this.showError(validation || apiError?.message || fallback);
  }

  private showError(message: string): void {
    this.toast.error(message);
  }

  private apiError(error: unknown): ApiError | null {
    return error instanceof HttpErrorResponse ? (error.error as ApiError) : null;
  }

  private compareByNameAndId(left: Group, right: Group): number {
    return this.compareStrings(left.name, right.name) || this.compareStrings(left.id, right.id);
  }

  private compareStrings(left: string, right: string): number {
    return left < right ? -1 : left > right ? 1 : 0;
  }
}
