#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

from django.utils.translation import ugettext as _

from childcount.forms import CCForm
from childcount.models import Patient
from childcount.models.reports import NeonatalReport
from childcount.exceptions import ParseError, BadValue, Inapplicable


class NeonatalForm(CCForm):
    KEYWORDS = {
        'en': ['n'],
    }

    def process(self, patient):

        days, weeks, months = patient.age_in_days_weeks_months()
        if days > 28:
            raise Inapplicable(_(u"Neonatal reports are only " \
                                  "for children less than 28 days old"))

        if len(self.params) < 2:
            raise ParseError(_(u"Not enough info, expected number of clinic " \
                                "visits since birth"))

        visits = self.params[1]
        if not visits.isdigit():
            raise BadValue(_("|Clinic visits since birth| must be a number"))
        visits = int(visits)

        chw = self.message.persistant_connection.reporter.chw
        nr = NeonatalReport(created_by=chw, patient=patient, \
                             clinic_visits=visits)
        nr.save()

        if visits == 0:
            self.response = _(u"No postnatal clinic visits since birth")
        elif visits == 1:
            self.response = _(u"One postnatal clinic visit since birth")
        elif visits > 1:
            self.response = _(u"%(visits)d postnatal clinic visit since " \
                               "birth") % {'visits': visits}