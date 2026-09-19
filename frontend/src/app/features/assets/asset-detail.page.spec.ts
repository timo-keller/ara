import { localDateTimeToUtc, reservationPayload } from './asset-detail.page';

describe('reservation date conversion', () => {
  it('converts a local date-time to a UTC instant', () => {
    const value = '2030-01-02T10:30';
    expect(localDateTimeToUtc(value)).toBe(new Date(value).toISOString());
  });

  it('omits ends_at for an open-ended reservation', () => {
    expect(reservationPayload('asset', '2030-01-02T10:30', '')).toEqual({
      asset_id: 'asset',
      starts_at: new Date('2030-01-02T10:30').toISOString(),
    });
  });
});
