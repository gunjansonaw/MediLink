"""
Booking domain logic shared by the REST API and the AI booking agent.
"""
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, Schedule

DAY_NAMES = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
DEFAULT_SLOT_MINUTES = 30


class SlotUnavailable(Exception):
    pass


def _parse_hhmm(value, default):
    try:
        return datetime.strptime(value, '%H:%M').time()
    except (TypeError, ValueError):
        return default


def working_windows(doctor, day: date):
    """
    Return [(start_time, end_time)] for a doctor on a given date.
    Explicit Schedule rows win; otherwise fall back to the DoctorProfile's
    available_days / available_hours ({"start": "09:00", "end": "17:00"}).
    """
    day_name = DAY_NAMES[day.weekday()]
    schedules = Schedule.objects.filter(doctor=doctor, is_active=True)
    if schedules.exists():
        return [(s.start_time, s.end_time) for s in schedules if s.day_of_week == day_name]

    profile = getattr(doctor, 'doctor_profile', None)
    if profile is None:
        return []
    days = [d.lower() for d in (profile.available_days or [])]
    if days and day_name not in days:
        return []
    hours = profile.available_hours or {}
    start = _parse_hhmm(hours.get('start'), time(9, 0))
    end = _parse_hhmm(hours.get('end'), time(17, 0))
    if not days and not hours:
        # No availability configured at all: assume standard weekday hours
        if day.weekday() >= 5:
            return []
    return [(start, end)] if start < end else []


def available_slots(doctor, start: date, end: date | None = None, slot_minutes=DEFAULT_SLOT_MINUTES, limit=200):
    """List free slots {date, time} for a doctor between start and end (inclusive)."""
    end = end or start
    if (end - start).days > 31:
        end = start + timedelta(days=31)
    now = timezone.localtime()
    booked = set(
        Appointment.objects.filter(
            doctor=doctor,
            appointment_date__range=(start, end),
            status__in=Appointment.ACTIVE_STATUSES,
        ).values_list('appointment_date', 'appointment_time')
    )
    slots = []
    day = start
    while day <= end and len(slots) < limit:
        for win_start, win_end in working_windows(doctor, day):
            cursor = datetime.combine(day, win_start)
            stop = datetime.combine(day, win_end)
            while cursor + timedelta(minutes=slot_minutes) <= stop:
                slot_time = cursor.time().replace(second=0, microsecond=0)
                aware = timezone.make_aware(cursor) if timezone.is_naive(cursor) else cursor
                if aware > now and (day, slot_time) not in booked:
                    slots.append({'date': day.isoformat(), 'time': slot_time.strftime('%H:%M')})
                cursor += timedelta(minutes=slot_minutes)
        day += timedelta(days=1)
    return slots[:limit]


def book_appointment(*, patient, doctor, appointment_date, appointment_time, reason, duration_minutes=30, notes=''):
    """
    Create an appointment atomically. The partial unique constraint on active
    slots is the real guard against races; we translate its IntegrityError.
    """
    try:
        with transaction.atomic():
            if Appointment.objects.select_for_update().filter(
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                status__in=Appointment.ACTIVE_STATUSES,
            ).exists():
                raise SlotUnavailable('This doctor is already booked for this date and time slot.')
            appointment = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                duration_minutes=duration_minutes,
                reason=reason,
                notes=notes,
            )
    except IntegrityError:
        raise SlotUnavailable('This doctor is already booked for this date and time slot.')
    return appointment
