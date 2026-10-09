import { Reservation } from './asset-catalogue.service';
import { availableBookingDurations } from './quick-booking';

describe('quick booking availability', () => {
  const now = new Date('2030-01-01T12:00:00Z').getTime();
  const reservation = (
    startHours: number,
    endHours: number | null,
    status: Reservation['status'] = 'active',
  ): Reservation => ({
    id: 'reservation',
    asset_id: 'asset',
    asset_name: null,
    asset_type: null,
    starts_at: new Date(now + startHours * 3_600_000).toISOString(),
    ends_at: endHours === null ? null : new Date(now + endHours * 3_600_000).toISOString(),
    status,
    lifecycle: null,
  });
  const hours = (reservations: Reservation[]) =>
    availableBookingDurations(reservations, now).map((duration) => duration.hours);

  it('blocks only durations which overlap an upcoming reservation', () => {
    expect(hours([reservation(2, 3)])).toEqual([1]);
    expect(hours([reservation(48, 49)])).toEqual([1, 24]);
    expect(hours([reservation(200, null)])).toEqual([1, 24, 168]);
  });

  it('allows adjacent reservations and ignores past and inactive bookings', () => {
    expect(hours([reservation(24, 25)])).toEqual([1, 24]);
    expect(hours([reservation(-1, 0)])).toEqual([1, 24, 168]);
    for (const status of ['cancelled', 'returned', 'ended'] as const) {
      expect(hours([reservation(0, null, status)])).toEqual([1, 24, 168]);
    }
  });

  it('blocks all durations during a current or open-ended reservation', () => {
    expect(hours([reservation(-1, 1)])).toEqual([]);
    expect(hours([reservation(-1, null)])).toEqual([]);
    expect(hours([reservation(0.5, null)])).toEqual([]);
  });
});
