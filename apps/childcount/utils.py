#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: dgelvin

import re
from datetime import date, timedelta
import itertools

from functools import wraps
from django.utils.translation import gettext as _

from childcount.exceptions import NotRegistered


class InvalidAge(Exception):
    pass


class InvalidDOB(Exception):
    pass


class Ambiguous(Exception):
    pass


class DOBProcessor:
    DAYS = 'd'
    WEEKS = 'w'
    MONTHS = 'm'
    YEARS = 'y'

    # Language specific age units.
    # IMPORTANT NOTE: List from shortest to longest
    UNITS = {}
    UNITS['en'] = {
        DAYS: ['d', 'day', 'days'],
        WEEKS: ['w', 'wk', 'wks', 'week', 'weeks'],
        MONTHS: ['m', 'mon', 'mths', 'month', 'months'],
        YEARS: ['y', 'yr', 'yrs', 'year', 'years'],
    }

    ABRV_MONTHS = {}
    ABRV_MONTHS['en'] = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', \
                         'jul', 'aug', 'sep', 'oct', 'nov', 'dec']

    #TODO Site specific stuff:
    #           Date order
    #           Round ages up or down
    DATEORDER = [DAYS, MONTHS, YEARS]
    ROUND_DOWN = True

    # Age (in years) beyond which we don't recognize
    MAX_AGE = 105

    @classmethod
    def from_age_or_dob(cls, lang, age_or_dob):
        age_or_dob = age_or_dob.strip().lower()

        if len(age_or_dob) == 0:
            return None, None

        # First of all, let's just keep everything in unicode
        if not isinstance(age_or_dob, unicode):
            age_or_dob = unicode(age_or_dob)

        try:
            dob, variance = cls.from_age(lang, age_or_dob)
        except InvalidAge:
            pass
        else:
            if cls.is_valid_dob(lang, age_or_dob):
                raise Ambiguous
            return dob, variance

        try:
            dob, variance = cls.from_dob(lang, age_or_dob)
        except InvalidDOB:
            return None, None
        else:
            return dob, variance

    @classmethod
    def is_valid_dob_or_age(cls, lang, age_or_dob):
        return cls.is_valid_dob(lang, age_or_dob) or \
               cls.is_valid_age(lang, age_or_dob)

    @classmethod
    def is_valid_dob(cls, lang, dob_string):
        try:
            dob, variance = cls.from_dob(lang, dob_string)
        except InvalidDOB:
            return False
        return True

    @classmethod
    def is_valid_age(cls, lang, age_string):
        try:
            dob, variance = cls.from_age(lang, age_string)
        except InvalidAge:
            return False
        return True

    @classmethod
    def get_age_units(cls, lang):
        if lang not in cls.UNITS:
            return None
        return list(itertools.chain(*cls.UNITS[lang].values()))

    @classmethod
    def from_dob(cls, lang, string):
        FIELD_DELIMTERS = ['\\', '/', '.', ',', '-']
        string = string.strip().lower()
        variance = 0

        delim_regex = '|'.join([re.escape(c) for c in FIELD_DELIMTERS])

        hit = False

        # now check for 15feb1980 or 12mar80
        months_regex = '|'.join([m.lower() for m in cls.ABRV_MONTHS[lang]])
        fields = {}
        fields[cls.DATEORDER.index(cls.YEARS)] = '(?P<y>\d{2,4})'
        fields[cls.DATEORDER.index(cls.MONTHS)] = '(?P<m>%s)' % months_regex
        fields[cls.DATEORDER.index(cls.DAYS)] = '(?P<d>\d{1,2})?'

        regex = r'%(a)s\s*(%(delims)s)?\s*%(b)s\s*(%(delims)s)?\s*%(c)s$' % \
                {'a': fields[0], 'b': fields[1], \
                 'c': fields[2], 'delims': delim_regex}
        match = re.match(regex, string)
        if match:
            hit = True
            grps = match.groups()
            string = ''
            for value in grps:
                if value and value.strip() in FIELD_DELIMTERS:
                    continue
                if value in cls.ABRV_MONTHS[lang]:
                    value = unicode(cls.ABRV_MONTHS[lang].index(value) + 1)
                if value:
                    if len(value) == 1 and value.isdigit():
                        value = '%02d' % int(value)
                    string = '%s%s/' % (string, value)
            string = string[:-1]

        # let's look for when they just do month  / (2 digit year)
        regex = r'(?P<m>\d{1,2})\s*(%s)?\s*(?P<y>\d{2})$' % delim_regex
        match = re.match(regex, string)

        # now let's look for when they just do month / (4 digit year)
        if not match:
            regex = r'(?P<m>\d{1,2})\s*(%s|\s)\s*(19|20)(?P<y>\d{2})$' % \
                                                                  delim_regex
            match = re.match(regex, string)

        if match and int(match.groupdict()['m']) <= 12:
            month = int(match.groupdict()['m'])
            year = int(match.groupdict()['y'])
            if date(int('2%03d' % year), month, 1) > date.today():
                year_prefix = 19
            else:
                year_prefix = 20
            year = int('%d%02d' % (year_prefix, year))
            variance = 15
            dob = date(year=year, month=month, day=15)

            if (date.today().year - dob.year) > cls.MAX_AGE:
                raise InvalidDOB
            return dob, variance


        if not hit:
            # Check if it is four digits 1901 (1 sep 2001 or 9 jan 2001)
            regex = r'(?P<a>\d{1})(?P<b>\d{1})(?P<c>\d{2})$'
            match = re.match(regex, string)
            if match:
                hit = True
                grps = match.groupdict()
                string = '%02d/%02d/%02d' % \
                    (int(grps['a']), int(grps['b']), int(grps['c']))

        if not hit:
            regex = r'(?P<a>\d{2})(?P<b>\d{1})(?P<c>\d{2})$'
            match = re.match(regex, string)
            if match:
                grps = match.groupdict()
                if int(match.groups()[cls.DATEORDER.index(cls.MONTHS)]) <= 12:
                    hit = True
                    string = '%s/%02d/%s' % (grps['a'], int(grps['b']), \
                                             grps['c'])
        if not hit:
            regex = r'(?P<a>\d{1})(?P<b>\d{2})(?P<c>\d{2})$'
            match = re.match(regex, string)
            if match:
                hit = True
                grps = match.groupdict()
                string = '%02d/%s/%s' % (int(grps['a']), grps['b'], grps['c'])
        if not hit:
            indexes = ['2', '2', '2']
            indexes[cls.DATEORDER.index(cls.YEARS)] = '4'

            regex = r'(?P<a>\d{%(a)s})(?P<b>\d{%(b)s})(?P<c>\d{%(c)s})$' % \
                        {'a': indexes[0], 'b': indexes[1], 'c': indexes[2]}

            match = re.match(regex, string)
            if match:
                hit = True
                grps = match.groupdict()
                string = '%s/%s/%s' % (grps['a'], grps['b'], grps['c'])
        if not hit:
            regex = r'(?P<a>\d{2})(?P<b>\d{2})(?P<c>\d{2})$'
            match = re.match(regex, string)
            if match:
                hit = True
                grps = match.groupdict()
                string = '%s/%s/%s' % (grps['a'], grps['b'], grps['c'])

        indexes = ['1,2', '1,2', '1,2']
        indexes[cls.DATEORDER.index(cls.YEARS)] = '2,4'

        regex = r'(?P<a>\d{%(a)s})\s*(%(d)s|\s)\s*(?P<b>\d{%(b)s})\s*' \
                 '(%(d)s|\s)\s*(?P<c>\d{%(c)s})$' % {'d': delim_regex, \
                  'a': indexes[0], 'b': indexes[1], 'c': indexes[2]}
        match = re.match(regex, string)
        if match:
            grps = match.groupdict()
            values = [grps['a'], grps['b'], grps['c']]
            year = int(values[cls.DATEORDER.index(cls.YEARS)])
            month = int(values[cls.DATEORDER.index(cls.MONTHS)])
            day = int(values[cls.DATEORDER.index(cls.DAYS)])

            if month > 12:
                raise InvalidDOB
            if len('%02d' % year) == 2:
                try:
                    dob = date(int('2%03d' % year), month, day)
                except ValueError:
                    raise InvalidDOB
                if dob > date.today():
                    year = int('19%02d' % year)
                else:
                    year = int('2%03d' % year)

            try:
                dob = date(year, month, day)
            except ValueError:
                raise InvalidDOB

            if (date.today().year - dob.year) > cls.MAX_AGE:
                raise InvalidDOB
            variance = 0
            return dob, variance

        # if we didn't return it yet, it's not valid
        raise InvalidDOB

    @classmethod
    def from_age(cls, lang, string):
        MONTH_IN_DAYS = 30.4368499
        MONTH_IN_WEEKS = 4.34812141
        YEAR_IN_DAYS = 365.242199
        YEAR_IN_WEEKS = 52.177457

        string = string.strip().lower()
        # first we will raise an exception if we find any character other
        # than an age unit, or . or / or spaces
        all_regex = '|'.join(cls.get_age_units(lang))

        if len(re.sub(r'\d|\s|\.|/|%s' % all_regex, '', string)) > 0 or \
        (string.isdigit() and (len(string) > 3 or int(string) > cls.MAX_AGE)):
            raise InvalidAge

        if string.isdigit():
            string = '%s%s' % (string, cls.UNITS[lang][cls.YEARS][0])


        # Reverse the lists so that we have the long unit
        # descriptions first
        for ls in [cls.DAYS, cls.WEEKS, cls.MONTHS, cls.YEARS]:
            cls.UNITS[lang][ls].reverse()

        days_regex = '|'.join(cls.UNITS[lang][cls.DAYS])
        weeks_regex = '|'.join(cls.UNITS[lang][cls.WEEKS])
        months_regex = '|'.join(cls.UNITS[lang][cls.MONTHS])
        years_regex = '|'.join(cls.UNITS[lang][cls.YEARS])

        # Match 3 3m as 3y 3m and 1 1/2m as 1y 1/2m and 1 1.2m as 1y 1.2m
        regex = r'(?P<y>\d{1,2})\s+(?P<m>\d(\s*([/.]\s*\d)?)\s*(%s))' % \
                                                               months_regex
        match = re.match(regex, string)
        if match:
            string = '%dy%s' % (int(match.groupdict()['y']), \
                                match.groupdict()['m'])

        # now that we've handled the one space delimeted field we recognize
        # let's strip all spaces.
        string = re.sub(r'\s', '', string)

        # if there is a duplicate unit, raise an error.  That doesn't make
        # sense; and I don't know how to handle it
        for regex in [days_regex, weeks_regex, months_regex, years_regex]:
            if len(re.findall(r'%s' % regex, string)) > 1:
                raise InvalidAge

        # Now let's put each string into a dict
        buckets = {}

        for key, regex in [(cls.DAYS, days_regex), \
                           (cls.WEEKS, weeks_regex), \
                           (cls.MONTHS, months_regex), \
                           (cls.YEARS, years_regex)]:
            regex = r'(?P<value>\d{1,3}([/.]\d{1,2})?)(%s)' % regex
            search = re.search(regex, string)
            if search:
                buckets[key] = search.groupdict()['value']

                # Replace fractions with decimals
                match = re.match(r'(\d+)/(\d+)', buckets[key])
                if match:
                    numerator, denominator = match.groups()
                    buckets[key] = round(float(numerator) / \
                                         float(denominator), 2)
                else:
                    buckets[key] = float(buckets[key])
            else:
                buckets[key] = 0

        # now get rid of fractions by dumping them into the bucket below.
        weeks_remainder = buckets[cls.WEEKS] % 1
        buckets[cls.DAYS] += weeks_remainder * 7
        buckets[cls.WEEKS] = int(buckets[cls.WEEKS])

        months_remainder = buckets[cls.MONTHS] % 1
        buckets[cls.WEEKS] += months_remainder * MONTH_IN_WEEKS
        buckets[cls.MONTHS] = int(buckets[cls.MONTHS])

        years_remainder = buckets[cls.YEARS] % 1
        buckets[cls.MONTHS] += years_remainder * 12
        buckets[cls.YEARS] = int(buckets[cls.YEARS])

        if buckets[cls.DAYS] > 0:
            variance = 1
            age_in_days = buckets[cls.DAYS] + buckets[cls.WEEKS] * 7 + \
                          buckets[cls.MONTHS] * MONTH_IN_DAYS + \
                          buckets[cls.YEARS] * YEAR_IN_DAYS
            dob = date.today() - timedelta(days=age_in_days)

        elif buckets[cls.WEEKS] > 0:
            variance = 3
            age_in_weeks = buckets[cls.WEEKS] + \
                           buckets[cls.MONTHS] * MONTH_IN_WEEKS + \
                           buckets[cls.YEARS] * YEAR_IN_WEEKS
            if cls.ROUND_DOWN:
                age_in_weeks += 0.5
            else:
                age_in_weeks -= 0.5
            dob = date.today() - timedelta(weeks=age_in_weeks)

        elif buckets[cls.MONTHS] > 0:
            variance = 15
            age_in_weeks = buckets[cls.MONTHS] * MONTH_IN_WEEKS + \
                           buckets[cls.YEARS] * YEAR_IN_WEEKS
            if cls.ROUND_DOWN:
                age_in_weeks += MONTH_IN_WEEKS * 0.5
            else:
                age_in_weeks -= MONTH_IN_WEEKS * 0.5
            dob = date.today() - timedelta(weeks=age_in_weeks)

        elif buckets[cls.YEARS] > 0:
            variance = 182
            age_in_weeks = buckets[cls.YEARS] * YEAR_IN_WEEKS
            if cls.ROUND_DOWN:
                age_in_weeks += YEAR_IN_WEEKS * 0.5
            else:
                age_in_weeks -= YEAR_IN_WEEKS * 0.5
            dob = date.today() - timedelta(weeks=age_in_weeks)
        else:
            raise InvalidAge

        if (date.today().year - dob.year) > cls.MAX_AGE:
            raise InvalidAge

        return dob, variance


def clean_names(flat_name, surname_first=True):

    '''
    Takes a persons name as a single string and returns surname,
    first names, and alias
        >>> clean_names("smith john")
        (u'Smith', u'John', u'jsmith')

    Also can be passed an optional argument surname_first=False:
        >>> clean_names("john ADAM smith", surname_first=False)
        (u'Smith', u'John Adam', u'jasmith')
    '''

    if not isinstance(flat_name, unicode):
        flat_name = unicode(flat_name)

    # Replace all occurances of 0 with o
    flat_name = re.sub('0', 'o', flat_name)

    # Replace all non-alphanumeric character with spaces
    flat_name = re.sub('\W_', ' ', flat_name)

    # Remove numbers
    flat_name = re.sub('\d', '', flat_name)

    # break up the name into a list
    names = re.findall('\w+', flat_name)

    surname = firstnames = alias = u''

    if names:
        pop_index = 0 if surname_first else -1
        surname = names.pop(pop_index).title()
        firstnames = ' '.join(names).title()
        alias = ''.join([c[0] for c in names] + [surname]).lower()

        if not names and not surname_first:
            surname, firstnames = firstnames, surname

    return surname, firstnames, alias

def authenticated(func):
    ''' decorator checking if sender is allowed to process feature.

    checks if sender property is set on message

    return function or boolean '''

    @wraps(func)
    def wrapper(self, *args):
        if self.message.persistant_connection.reporter:
            return func(self, *args)
        else:
            raise NotRegistered(_("%(number)s is not a registered number.")
                            % {'number': self.message.peer})
            return False
    return wrapper