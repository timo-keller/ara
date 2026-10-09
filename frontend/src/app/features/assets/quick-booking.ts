import { Reservation } from './asset-catalogue.service';

export const QUICK_BOOKING_DURATIONS = [
  { label: '1 hour', hours: 1 },
  { label: '1 day', hours: 24 },
  { label: '1 week', hours: 168 },
];

export function availableBookingDurations(reservations: Reservation[], now = Date.now()) {
  return QUICK_BOOKING_DURATIONS.filter(({ hours }) => {
    const end = now + hours * 3_600_000;
    return !reservations.some(
      (reservation) =>
        reservation.status === 'active' &&
        new Date(reservation.starts_at).getTime() < end &&
        (reservation.ends_at === null || new Date(reservation.ends_at).getTime() > now),
    );
  });
}
