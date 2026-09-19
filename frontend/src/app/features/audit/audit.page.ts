import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Params, Router } from '@angular/router';
import { SynAlertComponent } from '@synergy-design-system/angular/components/alert';
import { SynButtonComponent } from '@synergy-design-system/angular/components/button';
import { SynCardComponent } from '@synergy-design-system/angular/components/card';
import { SynDetailsComponent } from '@synergy-design-system/angular/components/details';
import { SynInputComponent } from '@synergy-design-system/angular/components/input';
import { SynOptionComponent } from '@synergy-design-system/angular/components/option';
import { SynPaginationComponent } from '@synergy-design-system/angular/components/pagination';
import { SynSelectComponent } from '@synergy-design-system/angular/components/select';
import { SynSpinnerComponent } from '@synergy-design-system/angular/components/spinner';
import { AuthService } from '../../core/auth/auth.service';
import { Group } from '../assets/asset-catalogue.service';
import { AssetAdministrationService } from '../assets/asset-administration.service';
import { AuditEvent, AuditFilters, AuditService, defaultAuditFilters } from './audit.service';

const secretKey = /(?:password|secret|token|credential|access[_-]?instructions)/i;

/** Convert a canonical UTC query value to the browser-local datetime-local representation. */
export function utcIsoToLocalDatetimeInput(value: string): string {
  if (!value) return '';
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.valueOf())) return '';
  const part = (number: number) => String(number).padStart(2, '0');
  return `${timestamp.getFullYear()}-${part(timestamp.getMonth() + 1)}-${part(timestamp.getDate())}T${part(timestamp.getHours())}:${part(timestamp.getMinutes())}`;
}

/** datetime-local has no zone; interpret the entered value in the browser's local time. */
export function localDatetimeInputToUtcIso(value: string): string {
  if (!value) return '';
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.valueOf()) ? value : timestamp.toISOString();
}

export function auditFiltersFromQuery(params: Params): AuditFilters {
  const defaults = defaultAuditFilters();
  const number = (name: string, fallback: number, min: number, max: number) => {
    const value = Number(params[name]);
    return Number.isInteger(value) && value >= min && value <= max ? value : fallback;
  };
  return {
    groupId: String(params['group_id'] ?? ''),
    actorId: String(params['actor_id'] ?? ''),
    action: String(params['action'] ?? ''),
    targetType: String(params['target_type'] ?? ''),
    targetId: String(params['target_id'] ?? ''),
    createdAtFrom: String(params['created_at_from'] ?? ''),
    createdAtTo: String(params['created_at_to'] ?? ''),
    offset: number('offset', defaults.offset, 0, Number.MAX_SAFE_INTEGER),
    limit: number('limit', defaults.limit, 1, 100),
  };
}

export function auditQueryParams(filters: AuditFilters): Params {
  const params: Params = {
    offset: filters.offset || null,
    limit: filters.limit === 25 ? null : filters.limit,
  };
  const names: [keyof Omit<AuditFilters, 'offset' | 'limit'>, string][] = [
    ['groupId', 'group_id'],
    ['actorId', 'actor_id'],
    ['action', 'action'],
    ['targetType', 'target_type'],
    ['targetId', 'target_id'],
    ['createdAtFrom', 'created_at_from'],
    ['createdAtTo', 'created_at_to'],
  ];
  for (const [key, name] of names) params[name] = filters[key].trim() || null;
  return params;
}

/** Render as text only and provide a second defence for accidentally returned sensitive fields. */
export function safeAuditJson(value: Record<string, unknown> | null): string {
  const redact = (candidate: unknown): unknown => {
    if (Array.isArray(candidate)) return candidate.map(redact);
    if (!candidate || typeof candidate !== 'object') return candidate;
    return Object.fromEntries(
      Object.entries(candidate).map(([key, item]) => [
        key,
        secretKey.test(key) ? '[redacted]' : redact(item),
      ]),
    );
  };
  return JSON.stringify(redact(value), null, 2);
}

@Component({
  imports: [
    DatePipe,
    SynAlertComponent,
    SynButtonComponent,
    SynCardComponent,
    SynDetailsComponent,
    SynInputComponent,
    SynOptionComponent,
    SynPaginationComponent,
    SynSelectComponent,
    SynSpinnerComponent,
  ],
  selector: 'app-audit-page',
  styleUrl: './audit.page.scss',
  templateUrl: './audit.page.html',
})
export class AuditPage {
  private readonly audit = inject(AuditService);
  private readonly groupService = inject(AssetAdministrationService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly groups = signal<Group[]>([]);
  readonly items = signal<AuditEvent[]>([]);
  readonly total = signal(0);
  readonly state = signal<'loading' | 'ready' | 'error'>('loading');
  readonly filters = signal(defaultAuditFilters());
  readonly selectableGroups = computed(() =>
    this.auth.roles()?.is_owner
      ? this.groups()
      : this.groups().filter((group) => this.auth.roles()?.group_roles[group.id] === 'group_admin'),
  );
  readonly page = computed(() => Math.floor(this.filters().offset / this.filters().limit) + 1);

  constructor() {
    this.groupService
      .groups()
      .subscribe({ next: ({ items }) => this.groups.set(items), error: () => undefined });
    this.route.queryParams.subscribe((params) => {
      const filters = auditFiltersFromQuery(params);
      this.filters.set(filters);
      this.load(filters);
    });
  }

  load(filters = this.filters()): void {
    this.state.set('loading');
    this.audit.list(filters).subscribe({
      next: (result) => {
        this.items.set(result.items);
        this.total.set(result.total);
        this.state.set('ready');
      },
      error: () => this.state.set('error'),
    });
  }

  changeFilter(
    name: keyof Omit<AuditFilters, 'offset' | 'limit'>,
    value: string | number | (string | number)[],
  ): void {
    const rawValue = String(value);
    const normalized =
      name === 'createdAtFrom' || name === 'createdAtTo'
        ? localDatetimeInputToUtcIso(rawValue)
        : rawValue;
    const filters = { ...this.filters(), [name]: normalized, offset: 0 };
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: auditQueryParams(filters),
    });
  }

  changePage(event: CustomEvent<{ currentPage: number }>): void {
    const filters = {
      ...this.filters(),
      offset: (event.detail.currentPage - 1) * this.filters().limit,
    };
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: auditQueryParams(filters),
    });
  }

  changePageSize(event: CustomEvent<{ currentPageSize: number }>): void {
    const filters = { ...this.filters(), limit: event.detail.currentPageSize, offset: 0 };
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: auditQueryParams(filters),
    });
  }

  groupName(groupId: string | null): string {
    return this.groups().find((group) => group.id === groupId)?.name ?? (groupId || 'No group');
  }
  stateJson(value: Record<string, unknown> | null): string {
    return safeAuditJson(value);
  }
  datetimeInputValue(value: string): string {
    return utcIsoToLocalDatetimeInput(value);
  }
}
