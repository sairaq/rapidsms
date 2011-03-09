#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 coding=utf-8
# maintainer: henrycg

import shutil

from celery.task import Task
from celery.task.schedules import crontab

from django.utils.translation import gettext as _
from django.http import HttpResponseRedirect, HttpResponseNotFound

from childcount.models import Configuration as Cfg
from childcount.reports.utils import report_filepath, report_url

REPORTS_DIR = 'reports'

# CREATING A NEW REPORT:
# 1) Subclass PrintedReport to create a new nightly
#    or on-demand report
# 2) Put your report file in reports/nightly or
#    reports/ondemand as desired
# 3) Add the name of your report as a Configuration
#    in the DB

class PrintedReport(Task):
   
    # Human-readable title of report
    title = None
    # Filename alphanumeric, underscore, and hyphen are ok
    filename = None
    # A list of file formats to use, e.g., ['pdf','html','xls']
    formats = []

    variants = [
        #(title_suffix, fn_suffix, variant_data)

        # For example, you might have a patient register
        # for Bugongi and Ruhiira health centers: 
        #(' Bugongi HC', '_BG', {'clinic_id': 13}),
        #(' Ruhiira HC', '_RH', {'clinic_id': 15}).
    ]

    # You should implement the generate method in a report
    # subclass.  This method creates the report and saves it
    # to the right place (probably static/reports/filename.format).
    # The return value is ignored.
    def generate(self, rformat, title, filepath, data):
        raise NotImplementedError(\
            _(u'Generate function not implemented.'))

    ####################
    # Unless you're an expert, you don't need to override
    # any of the rest of the methods in your subclass


    abstract = True
    def __init__(self):
        pass

    def run(self, *args, **kwargs):
        if len(self.formats) == 0:
            raise ValueError(\
                _(u'This report has no formats specified.'))

        if self.title is None or self.filename is None:
            raise ValueError(\
                _(u'Report title or filename is unset.'))
     
        # Check if a format was passed in
        rformat = kwargs.get('rformat')
        if rformat is None:
            formats = self.formats
        else:
            if rformat not in self.formats:
                raise ValueError('Invalid report format requested.')
            formats = [rformat]

        # Check if a variant was passed in
        variant = kwargs.get('variant')
        if variant is None:
            variants = self.variants
        else:
            variants = [variant]

        for rformat in formats:
            if len(variants) == 0:
                self.generate(rformat, \
                    self.title,
                    self.get_filepath(rformat),
                    {})
                continue

            for variant in variants:
                print variant
                self.generate(rformat, \
                    self.title + variant[0],
                    self.get_filepath(rformat, variant[1]),
                    variant[2])
    
    def get_filepath(self, rformat, file_suffix = ''):
        if self.filename is None:
            raise ValueError(\
                _(u'Report filename is unset.'))
        return report_filepath(self.filename + file_suffix, rformat)

    def report_view_data(self, rtype):
        if len(self.variants) == 0:
            return [self.one_report_view_data(rtype)]
        else:
            return map( \
                lambda v: \
                    self.one_report_view_data(rtype, v[0], v[1]),
                self.variants)


    def one_report_view_data(self, rtype, \
        tsuffix='', usuffix=''):
        if rtype not in ['nightly','ondemand']:
            raise ValueError("%s is invalid report type" \
                % rtype)
        return {
            'title': self.title+tsuffix,
            'url': ''.join([\
                '/childcount/reports/ondemand/'
                if rtype == 'ondemand' else
                '/static/childcount/reports/',\
                self.filename,\
                usuffix]),
            'types': self.formats
        }


#
# Misc.
#

def serve_ondemand_report(request, rname, rformat):
    print ">>%s" % rformat
    repts = report_objects('ondemand')

    # Find reports matching requests
    matches = filter(lambda rep: \
            (rname == rep.filename or \
                rname.startswith(rep.filename))
            and rformat in rep.formats,
        repts)

    if len(matches) == 0:
        return HttpResponseNotFound(request)

    report = matches[0]

    # If found, generate the report
    if rname == report.filename:
        result = report().apply(kwargs={'rformat':rformat})
    else:
        suffix = rname[len(report.filename):]

        variants = filter(lambda v: v[1] == suffix, report.variants)
        print variants
        if len(variants) == 0:
            return HttpResponseNotFound(request)
        result = report().apply(kwargs={\
            'rformat':rformat, 'variant': variants[0]})
    
    try:
        result.wait()
    except:
        print result.traceback
        raise

    if result.successful():
        # Redirect to static report
        return HttpResponseRedirect(report_url(rname, rformat))
    else:
        print result.traceback
        raise RuntimeError('Report generation failed')


def report_objects(folder):
    if folder not in ['nightly','ondemand']:
        raise ValueError('Folder specified must be "nightly" or "ondemand"')

    reports = []
    
    # Don't catch exception
    rvalues = Cfg.objects.get(key=folder+'_reports').value
    rnames = rvalues.split()
  
    print "Starting"
    for reporttype in rnames:
        print "Looking for module %s" % reporttype
        # Get childcount.reports.folder.report_name.Report
        try:
            rmod = __import__(\
                ''.join(['childcount.reports.definitions.',reporttype]),
                globals(), \
                locals(), \
                ['Report'], \
                -1)
        except ImportError:
            print "COULD NOT FIND MODULE %s" % reporttype
        else:
            print "Found module %s" % reporttype
            reports.append(rmod.Report)
    return reports

#
# View logic
#

def report_sets():
    report_sets = []

    tmp = map(
        lambda rep: rep().report_view_data('ondemand'),
        report_objects('ondemand'))
    on_demand = []
    for item in tmp:
        on_demand.extend(item)

    report_sets.append((_(u"On-Demand Reports"), on_demand))

    tmp = map(
        lambda rep: rep().report_view_data('nightly'),
        report_objects('nightly'))
    nightly = []
    for item in tmp:
        nightly.extend(item)
    report_sets.append((_(u"Nightly Reports"), nightly))

    return report_sets

