import { auditQuery, defaultAuditFilters } from './audit.service';

describe('auditQuery', () => {
  it('maps UI filters to the audit API contract and omits empty values', () => {
    const filters = {
      ...defaultAuditFilters(),
      groupId: 'group-1',
      actorId: 'actor-1',
      action: ['asset.update', 'asset.archive'],
      targetType: ['asset', 'group'],
      targetId: 'asset-1',
      createdAtFrom: '2026-01-01T00:00:00.000Z',
      createdAtTo: '2026-01-02T00:00:00.000Z',
      offset: 25,
      limit: 50,
    };
    expect(auditQuery(filters).toString()).toBe(
      'offset=25&limit=50&group_id=group-1&actor_id=actor-1&target_id=asset-1&created_at_from=2026-01-01T00:00:00.000Z&created_at_to=2026-01-02T00:00:00.000Z&action=asset.update&action=asset.archive&target_type=asset&target_type=group',
    );
  });
});
