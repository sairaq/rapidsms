#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
import time
from datetime import date

from django.utils.translation import ugettext as _
from ethiopian_date import EthiopianDateConverter

from childcount.forms import CCForm
from childcount.exceptions import BadValue, ParseError, InvalidDOB
from childcount.exceptions import Inapplicable
from childcount.models import Configuration
from childcount.models import Encounter
from childcount.models.reports import StillbirthMiscarriageReport
from childcount.utils import DOBProcessor
from childcount.forms.utils import MultipleChoiceField


class StillbirthMiscarriageForm(CCForm):
    """ Stillbirth Miscarriage Form

    Params:
        * Date of stillbirth or miscarriage('en' = yyyy-mm-dd
                                            'fr' = dd-mm-yyyy)
        * Type(SB/MC)
    """

    KEYWORDS = {
        'en': ['sbm'],
        'fr': ['sbm'],
    }
    ENCOUNTER_TYPE = Encounter.TYPE_PATIENT

    def process(self, patient):

        type_field = MultipleChoiceField()
        type_field.add_choice('en', \
                              StillbirthMiscarriageReport.TYPE_STILL_BIRTH, \
                              'SB')
        type_field.add_choice('en', \
                              StillbirthMiscarriageReport.TYPE_MISCARRIAGE, \
                              'MC')
        type_field.add_choice('fr', \
                              StillbirthMiscarriageReport.TYPE_STILL_BIRTH, \
                              'MN')
        type_field.add_choice('fr', \
                              StillbirthMiscarriageReport.TYPE_MISCARRIAGE, \
                              'AV')

        type_field.set_language(self.chw.language)
        if len(self.params) < 3:
            raise ParseError(_(u"Not enough info. Expected: Date of " \
                                "incident, then %(choices)s") % \
                                {'choices': type_field.choices_string()})

        try:
            sbmr = StillbirthMiscarriageReport.objects.get(\
                                                    encounter=self.encounter)
            sbmr.reset()
        except StillbirthMiscarriageReport.DoesNotExist:
            sbmr = StillbirthMiscarriageReport(encounter=self.encounter)
        sbmr.form_group = self.form_group

        type = self.params.pop()
        if not type_field.is_valid_choice(type):
            raise ParseError(_(u"You must indicate %(choices)s after the " \
                                "date.") % \
                                {'choices': type_field.choices_string()})
        sbmr.type = type_field.get_db_value(type)

        # import ethiopian date variable
        try:
            is_ethiopiandate = (Configuration.objects \
                                .get(key='inputs_ethiopian_date')\
                                .value.lower() == "true")
        except (Configuration.DoesNotExist, TypeError):
            is_ethiopiandate = False

        doi_str = ' '.join(self.params[1:])
        try:
            doi, variance = DOBProcessor.from_dob(self.chw.language, doi_str, \
                                                  self.date.date())
        except InvalidDOB:
            raise BadValue(_(u"Could not understand date: %(dod)s.") %\
                             {'dod': doi_str})

        # convert doi to gregorian before saving to DB
        if is_ethiopiandate and not variance:
            doi = EthiopianDateConverter.date_to_gregorian(doi)

        sbmr.incident_date = doi
        sbmr.save()

        self.response = _("Stillbirth or miscarriage on %(doi)s.") % \
                         {'doi': doi}
        sbmr.setup_reminders()
