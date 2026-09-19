import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, signal } from '@angular/core';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
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

@Component({
  imports: [
    SynAlertComponent,
    SynButtonComponent,
    SynCardComponent,
    SynInputComponent,
    SynOptionComponent,
    SynSelectComponent,
    SynSpinnerComponent,
    SynTextareaComponent,
  ],
  selector: 'app-administration-page',
  styleUrl: './administration.page.scss',
  templateUrl: './administration.page.html',
})
export class AdministrationPage {
  private readonly administration = inject(AdministrationService);
  readonly groups = signal<Group[]>([]);
  readonly mappings = signal<RoleMapping[]>([]);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly error = signal<string | null>(null);
  readonly archiveConflicts = signal<ApiErrorDetail[]>([]);
  readonly testResult = signal<boolean | null>(null);
  readonly groupDraft = signal<GroupDraft>({ id: null, name: '', description: '' });
  readonly mappingDraft = signal<MappingDraft>({
    id: null,
    group_id: '',
    expression: '',
    role: 'user',
    priority: '0',
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.state.set('loading');
    this.error.set(null);
    this.administration.groups().subscribe({
      next: ({ items }) => {
        this.groups.set(items);
        this.administration.mappings().subscribe({
          next: ({ items: mappings }) => {
            this.mappings.set(mappings);
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
  }

  saveGroup(): void {
    const draft = this.groupDraft();
    if (!draft.name.trim()) return this.showError('A group name is required.');
    const payload = { name: draft.name.trim(), description: draft.description || null };
    const request = draft.id
      ? this.administration.updateGroup(draft.id, payload)
      : this.administration.createGroup(payload);
    request.subscribe({
      next: () => this.resetGroupAndLoad(),
      error: (error) => this.showApiError(error),
    });
  }

  archiveGroup(group: Group): void {
    this.archiveConflicts.set([]);
    this.administration.archiveGroup(group.id).subscribe({
      next: () => this.load(),
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
      .subscribe({ next: () => this.load(), error: (e) => this.showApiError(e) });
  }

  changeMapping(
    field: keyof Omit<MappingDraft, 'id'>,
    value: string | number | (string | number)[],
  ): void {
    this.mappingDraft.update((draft) => ({ ...draft, [field]: String(value) }));
  }

  editMapping(mapping: RoleMapping): void {
    this.mappingDraft.set({
      id: mapping.id,
      group_id: mapping.group_id,
      expression: mapping.expression,
      role: mapping.role,
      priority: String(mapping.priority),
    });
  }

  saveMapping(): void {
    const draft = this.mappingDraft();
    if (!draft.group_id || !draft.expression.trim())
      return this.showError('Select a group and enter an expression.');
    const priority = Number(draft.priority);
    if (!Number.isInteger(priority) || priority < 0)
      return this.showError('Priority must be a whole number of zero or more.');
    const payload = {
      group_id: draft.group_id,
      expression: draft.expression.trim(),
      role: draft.role,
      priority,
      enabled: true,
    };
    const request = draft.id
      ? this.administration.updateMapping(draft.id, payload)
      : this.administration.createMapping(payload);
    request.subscribe({
      next: () => this.resetMappingAndLoad(),
      error: (error) => this.showApiError(error),
    });
  }

  disableMapping(mapping: RoleMapping): void {
    this.administration
      .disableMapping(mapping.id)
      .subscribe({ next: () => this.load(), error: (e) => this.showApiError(e) });
  }

  testMapping(): void {
    this.testResult.set(null);
    const expression = this.mappingDraft().expression.trim();
    if (!expression) return this.showError('Enter an expression to test.');
    this.administration.testExpression(expression).subscribe({
      next: ({ matches }) => this.testResult.set(matches),
      error: (error) => this.showApiError(error),
    });
  }

  groupName(groupId: string): string {
    return this.groups().find((group) => group.id === groupId)?.name ?? 'Unknown group';
  }

  private resetGroupAndLoad(): void {
    this.groupDraft.set({ id: null, name: '', description: '' });
    this.load();
  }

  private resetMappingAndLoad(): void {
    this.mappingDraft.set({ id: null, group_id: '', expression: '', role: 'user', priority: '0' });
    this.load();
  }

  private loadError(error: unknown): void {
    this.state.set('error');
    this.showApiError(error);
  }

  private showApiError(error: unknown): void {
    const apiError = this.apiError(error)?.error;
    const validation = apiError?.details
      ?.map((detail) => detail.message)
      .filter(Boolean)
      .join(' ');
    this.showError(validation || apiError?.message || 'The request could not be completed.');
  }

  private showError(message: string): void {
    this.error.set(message);
  }

  private apiError(error: unknown): ApiError | null {
    return error instanceof HttpErrorResponse ? (error.error as ApiError) : null;
  }
}
