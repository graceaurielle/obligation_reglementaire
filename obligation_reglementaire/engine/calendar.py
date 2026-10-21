"""Calendriers métier : jours ouvrés, fériés, ajout de délais, règle du jour non ouvré (Ch6, Ch13.18)."""

from datetime import timedelta

import frappe
from dateutil.relativedelta import relativedelta
from frappe.utils import cint, get_datetime, getdate

_WEEKDAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


class BusinessCalendar:
	def __init__(self, name=None):
		self.name = name
		self.working = {0, 1, 2, 3, 4}
		self.holidays = set()
		self.fuseau = None
		self.heure_limite = None
		if name and frappe.db.exists("Reg Calendar", name):
			cal = frappe.get_cached_doc("Reg Calendar", name)
			self.working = {i for i, f in enumerate(_WEEKDAYS) if cint(cal.get(f))} or {0, 1, 2, 3, 4}
			self.holidays = {getdate(h.date) for h in cal.jours_feries}
			self.fuseau = cal.fuseau_horaire
			self.heure_limite = cal.heure_limite

	def is_working_day(self, d):
		d = getdate(d)
		return d.weekday() in self.working and d not in self.holidays

	def next_working_day(self, d):
		d = getdate(d)
		for _ in range(400):
			if self.is_working_day(d):
				return d
			d += timedelta(days=1)
		return d

	def previous_working_day(self, d):
		d = getdate(d)
		for _ in range(400):
			if self.is_working_day(d):
				return d
			d -= timedelta(days=1)
		return d

	def add_working_days(self, d, n):
		d = getdate(d)
		step = 1 if n >= 0 else -1
		remaining = abs(cint(n))
		while remaining:
			d += timedelta(days=step)
			if self.is_working_day(d):
				remaining -= 1
		return d

	def working_days_between(self, start, end):
		start, end = getdate(start), getdate(end)
		if end <= start:
			return 0
		n, d = 0, start
		while d < end:
			d += timedelta(days=1)
			if self.is_working_day(d):
				n += 1
		return n

	def adjust(self, d, rule):
		"""Applique la règle « jour non ouvré » de l'obligation."""
		if not d:
			return d
		if rule == "Jour ouvré suivant":
			return self.next_working_day(d)
		if rule == "Jour ouvré précédent":
			return self.previous_working_day(d)
		return getdate(d)


def get_calendar(name=None):
	if not name:
		name = frappe.db.get_single_value("Reg Settings", "calendrier_defaut")
	return BusinessCalendar(name)


def add_delay(start, value, unit, calendar=None):
	"""Ajoute un délai à une date / date-heure de référence. Retourne une date."""
	value = cint(value)
	if not start:
		return None
	if not value:
		return getdate(start)
	cal = calendar or get_calendar()
	unit = unit or "Jours calendaires"
	if unit == "Minutes":
		return getdate(get_datetime(start) + timedelta(minutes=value))
	if unit == "Heures":
		return getdate(get_datetime(start) + timedelta(hours=value))
	start = getdate(start)
	if unit == "Jours ouvrés":
		return cal.add_working_days(start, value)
	if unit == "Semaines":
		return start + timedelta(weeks=value)
	if unit == "Mois":
		return start + relativedelta(months=value)
	if unit == "Trimestres":
		return start + relativedelta(months=3 * value)
	if unit == "Années":
		return start + relativedelta(years=value)
	return start + timedelta(days=value)


def describe_delay(value, unit):
	if not cint(value):
		return "à la date de référence"
	return f"{cint(value)} {(unit or 'Jours calendaires').lower()}"
