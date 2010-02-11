#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: ukanga

import re
import time
from datetime import date

from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.exceptions import BadValue, ParseError
from childcount.models.reports import DeathReport


class DeathForm(CCForm):
    KEYWORDS = {
        'en': ['dda'],
    }

    def process(self, patient):
        if len(self.params) < 2:
            raise ParseError(_(u"Not enough info, expected date of death"))

        created_by = self.message.persistant_connection.reporter.chw
        dod = self.params[1]

        dod_str = dod
        dod = re.sub(r'\D', '', dod)
        years_months = dod_str.replace(dod, '')
        if len(dod) >= 3:
            try:
                # TODO this 2 step conversion is too complex, simplify!
                dod = time.strptime(dod, "%d%m%y")
                dod = date(*dod[:3])
            except ValueError:
                try:
                    # TODO this 2 step conversion is too complex, simplify!
                    dod = time.strptime(dod, "%d%m%Y")
                    dod = date(*dod[:3])
                except ValueError:
                    raise BadValue(_("Couldn't understand date: %(dod)s")\
                                        % {'dod': dod})
        # if there are fewer than three digits, we are
        # probably dealing with an age (in months),
        # so attempt to estimate a dod
        else:
            # TODO move to a utils file? (almost same code in import_cases.py)
            try:
                if dod.isdigit():
                    if years_months.upper() == 'Y':
                        dod = int(dod) * 12
                    years = int(dod) / 12
                    months = int(dod) % 12
                    est_year = abs(date.today().year - int(years))
                    est_month = abs(date.today().month - int(months))
                    if est_month == 0:
                        est_month = 1
                    estimate = ("%s-%s-%s" % (est_year, est_month, 15))
                    # TODO this 2 step conversion is too complex, simplify!
                    dod = time.strptime(estimate, "%Y-%m-%d")
                    dod = date(*dod[:3])

            except Exception:
                pass
        print dod
        dr = DeathReport(created_by=created_by, patient=patient, \
                         death_date=dod)
        dr.save()

        response = _("died on %(dod)s") % {'dod': dod}
        #TODO - send alert to facilitators
        return response
