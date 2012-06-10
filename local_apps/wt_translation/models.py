import httplib2
import mimetools
import re

from datetime import datetime
from StringIO import StringIO
from xml.etree.ElementTree import ElementTree

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext_lazy as _

import pootle_store.util
import utils

from pootle_language.models import Language
from pootle_store.models import Store, Unit, Suggestion
from pootle_translationproject.models import TranslationProject
from wt_translation import TRANSLATOR_TYPES, SERVERLAND
from wt_translation import TRANSLATION_STATUSES, STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_FINISHED, STATUS_ERROR, STATUS_CANCELLED
from wt_translation import SERVERLAND_HOST_STATUSES, OK, INVALID_URL, INVALID_TOKEN, UNAVAILABLE, MISCONFIGURED_HOST

# Serverland integration
import xmlrpclib
import json
import pycountry


class LanguagePairManager(models.Manager):
    def get_by_natural_key(self, source_language, target_language):
        return LanguagePair.objects.get(
            source_language=source_language, target_language=target_language
            )


class LanguagePair(models.Model):
    source_language = models.ForeignKey(
        Language, related_name="source_language_ref"
        )
    target_language = models.ForeignKey(
        Language, related_name="target_language_ref"
        )

    objects = LanguagePairManager()

    def __unicode__(self):
        return u"%s :: %s" % (
            self.source_language.code, self.target_language.code
            )

    class Meta:
        unique_together = (("source_language", "target_language"),)


def get_or_create_language_pair(source_language, target_language):
    try:
        language_pair = LanguagePair.objects.get_by_natural_key(
            source_language, target_language
            )
    except (LanguagePair.DoesNotExist, IndexError):
        language_pair = LanguagePair()
        language_pair.source_language = source_language
        language_pair.target_language = target_language
        language_pair.save()
    return language_pair


class MachineTranslator(models.Model):
    shortname = models.CharField(_('Name'), max_length=50)
    supported_languages = models.ManyToManyField(LanguagePair)
    description = models.TextField(_('Description'))
    type = models.CharField(
        _('Type'), max_length=32, choices=TRANSLATOR_TYPES, default='Serverland'
        )
    timestamp = models.DateTimeField(_('Refresh Date'), default=datetime.now())

    def __unicode__(self):
        return u"%s :: %s" % (self.shortname, self.timestamp)

    def is_language_pair_supported(self, source_language, target_language):
        return self.supported_languages.filter(
            source_language = source_language,
            target_language = target_language
            ).exists()

    def create_translation_request(self, translation_project):
        '''
        Creates a translation request
        '''
        request = TranslationRequest()
        request.translator = self
        request.translation_project = translation_project
        request.save()
        return request

    @staticmethod
    def get_eligible_translators(source_language, target_language):
        """
        Get a list of translators that can be used to translate this
        language pair.
        """
        return MachineTranslator.objects.filter(
            supported_languages__source_language = source_language,
            supported_languages__target_language = target_language
            )

    def add_language_pair(self, source, target):
        iso = pycountry.languages
        try:
            source_code, target_code = (
                iso.get(bibliographic=source).alpha2,
                iso.get(bibliographic=target).alpha2
                )
            source = Language.objects.get_by_natural_key(source_code)
            target = Language.objects.get_by_natural_key(target_code)
            if not self.supported_languages.filter(
                source_language=source, target_language=target
                ):
                language_pair = get_or_create_language_pair(source, target)
                self.supported_languages.add(language_pair)
        except (AttributeError, Language.DoesNotExist):
            pass


class ServerlandHost(models.Model):
    shortname = models.CharField(_('Short Name'), max_length=100)
    description = models.TextField(_('Description'))
    url = models.URLField(
        _('URL Location'), verify_exists=True, max_length=255, unique=True
        )
    token = models.CharField(_('Auth Token'), max_length=8)
    timestamp = models.DateTimeField(_('Refresh Date'), default=datetime.now())
    status = models.CharField(
        _('Status'), max_length=1,
        choices=SERVERLAND_HOST_STATUSES, editable=False
        )
    translators = models.ManyToManyField(MachineTranslator)

    def __unicode__(self):
        return u"%s" % (self.url)

    def save(self):
        if self.id is None:
            super(ServerlandHost, self).save()
            try:
                self.sync()
            except Exception as e:
                print e
        else:
            self.timestamp = datetime.now()
            super(ServerlandHost, self).save()

    def sync(self):
        '''
        Synchronize a remote Serverland host and its translators (workers).
        '''
        workers = self.fetch_workers()
        for worker in workers:
            if eval(worker.find('is_alive').text):
                shortname = worker.find('shortname').text
                description = worker.find('description').text
                language_pairs = worker.find('language_pairs').getchildren()
                if not MachineTranslator.objects.filter(shortname=shortname):
                    mt = MachineTranslator.objects.create(
                        shortname=shortname, description=description
                        )
                    # Add language pairs
                    for lp in language_pairs:
                        source, target = tuple(
                            lang.text for lang in lp.getchildren()
                            )
                        mt.add_language_pair(source, target)
                    self.translators.add(mt)
                    self.status = OK
                    self.save()

    def request(self, url, method='GET', body=None, header=None):
        HTTP = httplib2.Http()
        if body and header:
            return HTTP.request(url, method=method, body=body, headers=header)
        else:
            return HTTP.request(url, method=method)

    def element_tree(self, response): # make private (?)
        xml = response[1]
        xmlfile = StringIO(xml)
        return ElementTree(file=xmlfile)

    def fetch_workers(self):
        url = self.url + 'workers/?token=%s' % self.token
        response = self.request(url)
        et = self.element_tree(response)
        return et.findall('resource')

    def request_translation(self, trans_request):
        translator = trans_request.translator
        source_lang = trans_request.translation_project.project.source_language
        target_lang = trans_request.translation_project.language
        if not translator.is_language_pair_supported(source_lang, target_lang):
            raise UnsupportedLanguagePair(
                translator, source_lang, target_lang
                )

        if translator.type == SERVERLAND:
            request_id = utils.generate_request_id()
            shortname = 'wt_%s' % request_id
            src = utils.get_iso639_2(source_lang.code)
            tgt = utils.get_iso639_2(target_lang.code)
            contents = {
                'token': str(self.token),
                'shortname': str(shortname),
                'worker': str(translator.shortname),
                'source_language': str(src),
                'target_language': str(tgt)
                }
            source_file_id = "%s-%s-%s" % (
                request_id, source_lang.code, target_lang.code
                )
            store = Store.objects.get(
                translation_project=trans_request.translation_project
                )
            sentences = [unicode(unit) for unit in store.units]

            boundary = '-----' + mimetools.choose_boundary() + '-----'
            body = utils.generate_request_body(
                boundary, contents, source_file_id, sentences
                )
            header = utils.generate_request_header(boundary, body)

            response = self.request(
                str(self.url) + 'requests/', method='POST',
                body=body, header=header
                )

            print 'Submitted new request...'
            print '=> Response status:', response[0].status
            print '=> Reason:', response[0].reason
            print '=> Shortname:', shortname

            trans_request.external_id = shortname
            trans_request.status = STATUS_IN_PROGRESS
            trans_request.save()


    def fetch_translations(self):
        response = self.request(
            self.url + 'requests/?token={0}'.format(self.token)
            )
        if response[0].status == 200:
            et = self.element_tree(response)
            requests = et.findall('resource')
            completed_requests = (
                r for r in requests if eval(r.findtext('ready'))
                )
            in_progress_requests = set([
                tr.external_id for tr in
                TranslationRequest.objects.filter(status=STATUS_IN_PROGRESS)
                ])
            for request in completed_requests:
                shortname = request.findtext('shortname')
                if shortname in in_progress_requests:
                    tr = TranslationRequest.objects.get_by_external_id(
                        shortname
                        )
                    response = self.request(
                        self.url + 'results/{0}/?token={1}'.format(
                            shortname, self.token
                            )
                        )
                    et = self.element_tree(response)
                    result = et.findtext('result')
                    result_sentences = [
                        sentence.strip() for sentence in
                        utils.clean_string(result.strip()).split('\n')
                        ]
                    store = Store.objects.get(
                        translation_project=tr.translation_project
                        )
                    units = store.unit_set.all()
                    if not len(units) == len(result_sentences):
                        tr.status = STATUS_ERROR
                        print 'ERROR!'
                    else:
                        for i in range(len(units)):
                            units[i].target = result_sentences[i]
                            units[i].state = pootle_store.util.FUZZY
                            units[i].save()
                        tr.status = STATUS_FINISHED
                    tr.save()
        else:
            raise Exception(response[0].reason)


class TranslationRequestManager(models.Manager):
    def get_by_external_id(self, external_id):
        return TranslationRequest.objects.get(external_id = external_id)


class TranslationRequest(models.Model):
    translation_project = models.ForeignKey(TranslationProject)
    translator = models.ForeignKey(
        MachineTranslator, related_name='requested_translator'
        )
    status = models.CharField(
        _('Request Status'), max_length=32,
        choices=TRANSLATION_STATUSES, default = STATUS_PENDING
        )
    external_id = models.CharField(
        _('External ID'), max_length=32, editable=False, null=True
        )
    timestamp = models.DateTimeField(_('Last Updated'), default=datetime.now())

    objects = TranslationRequestManager()

    class Meta:
        unique_together = ("translation_project", "translator")

    def __unicode__(self):
        return u"%s - %s" % (self.translator.shortname, self.translation_project)

    def save(self):
        super(TranslationRequest, self).save()


class UndefinedTranslator(Exception):
    def __init__(self, value):
        if isinstance(value, MachineTranslator):
            self.value = "Machine Translator %s is not completely defined." % value
        else:
            self.value = "This Machine Translator is undefined. %s" % value
    def __str__(self):
        return repr(self.value)


class UnsupportedLanguagePair(Exception):
    def __init__(self, translator, source_language, target_language):
        self.value = "Machine Translator %s does not support the language pair (%s, %s)." % (translator, source_language.code, target_language.code)

    def __str__(self):
        return repr(self.value)


class TranslatorConfigError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return repr(self.msg)


class ServerlandConfigError(TranslatorConfigError):
    def __init__(self, host, error):

        self.errorCode = UNAVAILABLE

        if isinstance(host, ServerlandHost):
            # Inspect the XML-RPC error type. It can either be a Fault or a ProtocolError
            if isinstance(error, xmlrpclib.ProtocolError):
                self.errorCode = INVALID_URL
                self.msg = "Invalid Serverland host URL: '%s'." % host.url
            elif isinstance(error, xmlrpclib.Fault):
                # Inspect the faultCode and faultString to determine the error
                if re.search("[Errno 111] Connection refused", error.faultString) != None:
                    self.errorCode = INVALID_TOKEN
                    self.msg = "Invalid authentication token for Serverland host '%s'." % host.shortname
                elif re.search("[Errno 111] Connection refused", error.faultString) != None:
                    self.errorCode = UNAVAILABLE
                elif re.search("takes exactly \d+ arguments", error.faultString) != None:
                    self.errorCode = MISCONFIGURED_HOST
                    self.msg = "Serverland host '%s' is misconfigured." % host.shortname
                else:
                    self.msg = error.faultString

#            if self.errorCode == UNAVAILABLE:
#                self.msg = "Serverland host '%s' is unavailable." % host.shortname

            # TODO: Should updating the ServerlandHost instance go here? And if the host is unavailable, should we update the status as such? For now, assume yes.
            host.status = self.errorCode
            host.save()
        else:
            super(TranslatorConfigError, self).__init__(host)


def send_translation_requests():
    '''
    Sends a batch of machine translation requests.
    '''
    pending_requests = TranslationRequest.objects.filter(status=STATUS_PENDING)
    serverland_host = ServerlandHost.objects.get(id=1)
    for request in pending_requests:
        serverland_host.request_translation(request)
