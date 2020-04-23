import dateutil
import holidays
import logging
import datetime
import pandas as pd
from dateutil import rrule


class BSUCalendar(object):
    def __init__(self, start_year=2012, end_year=None, log_level="ERROR"):
        """Get important dates on Ball State University's Academic Calendar
        
        Repeating rules for dates were determined by hand, recognizing patterns
        in academic calendars posted online. Only checked back to 2012.
        
        Parameters
        ----------
        start_year : int
            First academic year to produce dates (e.g. 2019 == '2019-2020 academic year')
        end_year : int
            Last academic year to produce dates

        """
        self._set_logger(log_level)
        self.semesters = ["Fall", "Spring", "Summer"]
        self.sem_code_to_int = {"Fall": 10, "Spring": 20, "Summer": 30}
        self.int_to_sem_code = {v: k for k, v in self.sem_code_to_int.items()}

        self.holidays = (
            "Thanksgiving Break",
            "Labor Day",
            "MLK Day",
            "Memorial Day",
            "Independence Day",
        )

        self.tags = {
            "Registration": (
                "Late Registration Start",
                "Late Registration End",
                "Withdraw Deadline",
            ),
            "Instruction": (
                "Classes Start",
                "Classes End",
                "Break Start",
                "Break End",
                "Finals Start",
                "Finals End",
                "Final Grades Due",
            ),
            "Holidays": self.holidays,
        }
        # TODO: "Midterm Grades Due", for Instruction

        if start_year < 2012:
            self._logger.warning("Dates have not been validated prior to 2012")
        self.min_date = datetime.date(start_year, 8, 1)
        if end_year is None:
            end_year = datetime.datetime.now().year + 2
        self.max_date = datetime.date(end_year, 8, 1)

        self.years = list(range(self.min_date.year, self.max_date.year))
        self.n_yrs = len(self.years)
        # self.terms = [ 100*yr + sem for yr in self.years for sem in [10, 20, 30] ]

        # Midterm grade due

        term_length = datetime.timedelta(days=116)
        sum_term_length = datetime.timedelta(days=68)
        xmas_break = datetime.timedelta(days=24)

        # Generators that yield holidays and special days
        timeframe = dict(dtstart=self.min_date, count=self.n_yrs)
        thanksgiving = self._thanksgiving(**timeframe)
        labor_day = self._labor_day(**timeframe)
        mlk_day = self._mlk_day(**timeframe)
        memorial_day = self._memorial_day(**timeframe)
        independence_day = self._independence_day(**timeframe)

        fall_start = self._fall_start(**timeframe)
        fall_break_start = self._fall_break_start(**timeframe)
        spring_withdraw = self._spring_withdraw_deadline(**timeframe)

        # should return a dataframe with columns:
        # Term, Year, Semester, DateName, Date, Tags

        self.dates = {}
        for yr in self.years:
            # dues for this academic year
            yr_dates = {}

            # fall term
            f_start = next(fall_start)
            f_end = f_start + term_length

            f_break_start = next(fall_break_start)
            f_break_end = self._add_days(f_break_start, 1)
            f_withdraw_end = self._add_days(f_break_end, 1)

            f_thank_break_start = self._add_days(next(thanksgiving), -1)
            f_thank_break_end = self._add_days(f_thank_break_start, 2)

            yr_dates["Fall Term Start"] = f_start
            yr_dates["Fall Classes Start"] = f_start
            yr_dates["Fall Late Registration Start"] = f_start
            yr_dates["Fall Late Registration End"] = self._add_days(f_start, 4)
            yr_dates["Fall Break Start"] = f_break_start
            yr_dates["Fall Break End"] = f_break_end
            yr_dates["Fall Withdraw Deadline"] = f_withdraw_end
            yr_dates["Thanksgiving Break Start"] = f_thank_break_start
            yr_dates["Thanksgiving Break End"] = f_thank_break_end
            yr_dates["Labor Day"] = next(labor_day)
            yr_dates["Fall Classes End"] = self._add_days(f_end, -4)
            yr_dates["Fall Finals Start"] = self._add_days(f_end, -3)
            yr_dates["Fall Finals End"] = f_end
            yr_dates["Fall Term End"] = f_end
            yr_dates["Fall Final Grades Due"] = self._add_days(f_end, 3)

            # spring term
            sp_start = self._add_days(f_end, xmas_break)
            sp_end = self._add_days(sp_start, term_length)
            if yr == 2013:
                sp_break_start = sp_start + datetime.timedelta(weeks=9)
            else:
                sp_break_start = sp_start + datetime.timedelta(weeks=8)

            yr_dates["Spring Term Start"] = sp_start
            yr_dates["Spring Classes Start"] = sp_start
            yr_dates["Spring Break Start"] = sp_break_start
            yr_dates["Spring Break End"] = self._add_days(sp_break_start, 4)
            yr_dates["Spring Withdraw Deadline"] = next(spring_withdraw)
            yr_dates["Spring Classes End"] = self._add_days(sp_end, -4)
            yr_dates["Spring Finals Start"] = self._add_days(sp_end, -3)
            yr_dates["Spring Finals End"] = sp_end
            yr_dates["Spring Term End"] = sp_end
            yr_dates["Spring Final Grades Due"] = self._add_days(sp_end, 3)

            # summer term
            sm_start = self._add_days(sp_end, 10)
            sm_end = self._add_days(sp_start, sum_term_length)

            yr_dates["Summer Term Start"] = sm_start
            yr_dates["Independenc Day"] = next(independence_day)
            # missing dates here
            yr_dates["Summer Term End"] = sm_end
            yr_dates["Summer Final Grades Due"] = self._add_days(sm_end, 3)

            self.dates[yr] = yr_dates

    def date_in_term(self, term, field):
        """Get a date in a term"""
        if isinstance(term, str):
            term = int(term)
        yr = int(round(term, -2) / 100)
        return self.dates[yr][field]

    def dates_by_tag(self, tag):
        """Get all dates for a tag"""
        yr = int(round(term, -2) / 100)
        sem = self.int_to_sem_code(term - round(term, -2))
        if tag in self.tags:
            fields = self.tags[tag]
            if tag == "Holidays":
                vals = {}
                for hol in self.holidays:
                    if hol == "Thanksgiving Break":
                        hol_d = self.get_holiday(hol.rstrip(" Break"))
                        vals[hol + " Start"] = self._add_days(hol_d, -1)
                        vals[hol + " End"] = self._add_days(hol_d, 1)
                    else:
                        vals[hol] = self.get_holiday(hol)
            else:
                vals = {
                    f"{sem} {fld}": self.dates[f"{sem} {fld}"]
                    for sem in self.semesters
                    for fld in fields
                }
            return vals
        else:
            ValueError(
                f"{tag} not valid. Choose from: {list(self.tags.keys()).__str__()}"
            )

    def get_holiday(self, holiday, ac_year):
        """Return the date of a holiday for a given academic year"""
        attr_name = "_" + holiday.lower().replace(" ", "_")
        if hasattr(self, attr_name):
            gen_holiday = getattr(self, attr_name)
            if holiday in ["MLK Day", "Memorial Day", "Independence Day"]:
                ac_year += 1
            return list(gen_holiday(dtstart=datetime.date(ac_year, 1, 1), count=1))[0]
        else:
            raise ValueError(f"Holiday {holiday} not recognized")

    def _set_logger(self, level):
        """Create logger with level"""
        logger = logging.getLogger("bsu_dates")
        logger.setLevel(level)
        ch = logging.StreamHandler()
        logger.addHandler(ch)
        self._logger = logger

    def _add_days(self, d, days):
        """Add timedelta or integer number of days to a date"""
        if isinstance(days, int):
            return d + datetime.timedelta(days=days)
        elif isinstance(days, datetime.timedelta):
            return d + days
        else:
            raise ValueError("days argument must be type int or datetime.timedelta")

    def _irule(self, **kwargs):
        """Return iterator for dates defined by a repeating rule
        
        See: dateutil.rrule docs on defining repeating rules
        """
        assert "freq" in kwargs, "Must have freq argument"

        kwargs = {key: val for key, val in kwargs.items() if not val is None}

        self._logger.debug("_irule args: " + kwargs.__str__())

        freq = kwargs.pop("freq")

        if not ("until" in kwargs or "count" in kwargs):
            if "until" in kwargs and "count" in kwargs:
                raise ValueError("Specify either count or until, not both")
            else:
                raise ValueError("Must specify either count or until.")

        return iter(rrule.rrule(freq, **kwargs))

    def _thanksgiving(self, dtstart=None, until=None, count=None):
        """Thanksgiving is the last thursday of every november"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 11,
            "byweekday": rrule.TH(4),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _labor_day(self, dtstart=None, until=None, count=None):
        """Labor day is the first monday of September"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 9,
            "byweekday": rrule.MO(1),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _mlk_day(self, dtstart=None, until=None, count=None):
        """MLK day is the third monday of January"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 1,
            "byweekday": rrule.MO(3),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _memorial_day(self, dtstart=None, until=None, count=None):
        """Memorial day is the last monday of March"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 3,
            "byweekday": rrule.MO(-1),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _independence_day(self, dtstart=None, until=None, count=None):
        """Independence day is the 4th of July"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 7,
            "bymonthday": 4,
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _fall_start(self, dtstart=None, until=None, count=None):
        """Fall term starts the second to last Monday of August"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 8,
            "byweekday": rrule.MO(-2),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _fall_break_start(self, dtstart=None, until=None, count=None):
        """Fall break starts the second to last Monday of October"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 10,
            "byweekday": rrule.MO(-2),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)

    def _spring_withdraw_deadline(self, dtstart=None, until=None, count=None):
        """Spring withdraw deadline is the third Monday in March"""
        kwargs = {
            "freq": rrule.YEARLY,
            "bymonth": 3,
            "byweekday": rrule.MO(3),
            "dtstart": dtstart,
            "until": until,
            "count": count,
        }
        return self._irule(**kwargs)
