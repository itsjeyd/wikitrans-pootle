from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import iri_to_uri
from django.conf import settings
from django.contrib.auth.models import User
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist

from pootle_language.models import Language
from pootle_translationproject.models import TranslationProject
from pootle_store.models import Store, Unit, Suggestion
import pootle_store.util

from wt_translation import TRANSLATOR_TYPES, SERVERLAND
from wt_translation import TRANSLATION_STATUSES, STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_FINISHED, STATUS_ERROR, STATUS_CANCELLED
from wt_translation import SERVERLAND_HOST_STATUSES, OK, INVALID_URL, INVALID_TOKEN, UNAVAILABLE, MISCONFIGURED_HOST
import utils

import re

# Serverland integration
import xmlrpclib
import json
import pycountry
import errno

class LanguagePairManager(models.Manager):
    def get_by_natural_key(self, source_language, target_language):
        return LanguagePair.objects.get(source_language=source_language, target_language=target_language)

# TODO: Do I need this?
class LanguagePair(models.Model):
    source_language = models.ForeignKey(Language, related_name="source_language_ref")
    target_language = models.ForeignKey(Language, related_name="target_language_ref")

    objects = LanguagePairManager()

    def __unicode__(self):
        return u"%s :: %s" % (self.source_language.code, self.target_language.code)

    class Meta:
        unique_together = (("source_language", "target_language"),)

# Get or create a language pair
def get_or_create_language_pair(source_language, target_language):
    try:
        # Try to get the language pair
        language_pair = LanguagePair.objects.get_by_natural_key(source_language, target_language)
#        language_pair = LanguagePair.objects.filter(source_language = source_language, target_language = target_language)[0]
    except (LanguagePair.DoesNotExist, IndexError):
        # The language pair doesn't exist. Create it.
        language_pair = LanguagePair()
        language_pair.source_language = source_language
        language_pair.target_language = target_language
        language_pair.save()

    return language_pair

class MachineTranslator(models.Model):
    shortname = models.CharField(_('Name'), max_length=50)
    supported_languages = models.ManyToManyField(LanguagePair)
    description = models.TextField(_('Description'))
    type = models.CharField(_('Type'), max_length=32, choices=TRANSLATOR_TYPES, default='Serverland')
    timestamp = models.DateTimeField(_('Refresh Date'), default=datetime.now())

    def __unicode__(self):
        return u"%s :: %s" % (self.shortname, self.timestamp)

    def is_language_pair_supported(self, source_language, target_language):
        return self.supported_languages.filter(source_language = source_language,
                                               target_language = target_language).exists()

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
        Get a list of translators that can be used to translate this language pair.
        """
        return MachineTranslator.objects.filter(
                                supported_languages__source_language = source_language,
                                supported_languages__target_language = target_language
                            )

class ServerlandHost(models.Model):
    shortname = models.CharField(_('Short Name'), max_length=100)
    description = models.TextField(_('Description'))
    url = models.URLField(_('URL Location'), verify_exists=True, max_length=255, unique=True)
    token = models.CharField(_('Auth Token'), max_length=8)
    timestamp = models.DateTimeField(_('Refresh Date'), default=datetime.now())
    status = models.CharField(_('Status'), max_length=1, choices=SERVERLAND_HOST_STATUSES, editable=False)

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
        Add or synchronize a remote Serverland XML-RPC host and its translators (workers).
        '''
        # Fetch information about workers
        import httplib2
        from StringIO import StringIO
        from xml.etree.ElementTree import ElementTree

        HTTP = httplib2.Http()
        response = HTTP.request(
            self.url + 'workers/?token=%s' % self.token, method='GET'
            )
        xml = response[1]

        # Turn string containing XML response into a file-like object
        xmlfile = StringIO(xml)

        # Create traversable ElementTree from file object
        et = ElementTree(file=xmlfile)

        # Workers are "resources", so:
        workers = et.findall('resource')

        for worker in workers:
            # Extract relevant info from workers that are alive
            if eval(worker.find('is_alive').text):
                shortname = worker.find('shortname').text
                description = worker.find('description').text
                # is_busy = worker.find('is_busy').text
                language_pairs = worker.find('language_pairs').getchildren()
                # Create new MachineTranslator object and save to WT database
                if not MachineTranslator.objects.filter(shortname=shortname):
                    mt = MachineTranslator()
                    mt.shortname = shortname
                    mt.description = description
                    mt.save()
                    # Add language pairs
                    iso = pycountry.languages
                    for lp in language_pairs:
                        lang1, lang2 = tuple(lang.text for lang in lp.getchildren())
                        print lang1, lang2
                        try:
                            code1, code2 = (iso.get(bibliographic=lang1).alpha2, iso.get(bibliographic=lang2).alpha2)
                            lang1 = Language.objects.get_by_natural_key(code1)
                            lang2 = Language.objects.get_by_natural_key(code2)
                            if not mt.supported_languages.filter(source_language=lang1, target_language=lang2):
                                language_pair = get_or_create_language_pair(lang1, lang2)
                                mt.supported_languages.add(language_pair)
                        except AttributeError:
                            continue
                        except Language.DoesNotExist:
                            continue
                    self.translators.add(mt)
                    self.status = OK
                    self.save()



    # Reimplementation of ServerlandHost.fetch_translations method
    def fetch_translations(self):
        import httplib2
        from StringIO import StringIO
        from xml.etree.ElementTree import ElementTree
        HTTP = httplib2.Http()
        # First step: Get list of results for registered token
        url = self.url + 'requests/?token={0}'.format(self.token)
        response = HTTP.request(url, method='GET')
        if response[0].status == 200:
            xml = response[1]
            xmlfile = StringIO(xml)
            et = ElementTree(file=xmlfile)
            requests = et.findall('resource')
            # Filter response for completed requests
            completed_requests = (
                r for r in requests if eval(r.findtext('ready'))
                )
            external_ids = set(
                [tr.external_id for tr in TranslationRequest.objects.all()]
                )
            # Process completed requests one by one
            for request in completed_requests:
                shortname = request.findtext('shortname')
                if shortname in external_ids:
                    tr = TranslationRequest.objects.get_by_external_id(
                        shortname
                        )
                    if tr.status == STATUS_FINISHED:
                        continue
                    url = self.url + 'results/{0}/?token={1}'.format(
                        shortname, self.token)
                    response = HTTP.request(url, method='GET')
                    xml = response[1]
                    xmlfile = StringIO(xml)
                    et = ElementTree(file=xmlfile)
                    result = et.findtext('result')
                    result_sentences = utils.clean_string(result.strip()).split('\n')
                    result_sentences = [s.strip() for s in result_sentences]
                    store = Store.objects.get(
                        translation_project=tr.translation_project)
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
    translator = models.ForeignKey(MachineTranslator, related_name='requested_translator')
    status = models.CharField(_('Request Status'),
                              max_length=32,
                              choices=TRANSLATION_STATUSES,
                              default = STATUS_PENDING)
    external_id = models.CharField(_('External ID'), max_length=32, editable=False, null=True)
    timestamp = models.DateTimeField(_('Last Updated'), default=datetime.now())

    objects = TranslationRequestManager()

    class Meta:
        unique_together = ("translation_project", "translator")

    def __unicode__(self):
        return u"%s - %s" % (self.translator.shortname, self.translation_project)

    def save(self):
        # Last step, call the normal save method
        super(TranslationRequest, self).save()

def send_translation_requests(request_status=STATUS_PENDING):
    '''
    Sends a batch of machine translation requests.
    '''
    pending_requests = TranslationRequest.objects.filter(status=request_status)
    for request in pending_requests:

        # Get the .po store for the file to be translated
        store = Store.objects.get(
            translation_project=request.translation_project
            )

        # Get all of the sentences; store.unit_set.all() returns the
        # sentences in order.
        sentences = [unicode(unit) for unit in store.units]

        # Request the translation
        external_request_id = request_translation(
            request.translator,
            sentences,
            request.translation_project.project.source_language,
            request.translation_project.language
            )

        # Update the status of the record
        request.external_id = external_request_id
        request.status = STATUS_IN_PROGRESS
        request.save()

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

def request_translation(translator, sentences, source_language, target_language):
    """
    Request a MachineTranslator to perform a translation. The request
    process is implemented based on the type of MachineTranslator. For
    example, a SERVERLAND type uses a MT Server Land to request a
    translation.

    Preconditions:
        translator:    A MachineTranslator object.
        sentences:     A list of strings.

    Exceptions:
        UnsupportedLanguagePair:
            - The target translator doesn't support the language pair.
        UndefinedTranslator:
            - When looking up the ServerlandHost for a
              MachineTranslator, if none exists (this should not
              happen).
        ServerlandConfigError:
            - The ServerlandHost has an error.
    """
    if not translator.is_language_pair_supported(
        source_language, target_language
        ):
        raise UnsupportedLanguagePair(
            translator, source_language, target_language
            )

    request_id = utils.generate_request_id()
    sentences = utils.cast_to_list(sentences)
    text = "\n".join(sentences)
    source_file_id = "%s-%s-%s" % (
        request_id, source_language.code, target_language.code
        )

    if translator.type == SERVERLAND:
        try:
            serverland_host = translator.serverlandhost_set.all()[0]
        except IndexError:
            raise UndefinedTranslator(translator)

        result = send_trans_request(
            serverland_host.token,
            request_id,
            translator.shortname,
            utils.get_iso639_2(source_language.code),
            utils.get_iso639_2(target_language.code),
            source_file_id,
            text
            )
        print result
        return request_id


def send_trans_request(token, request_id, worker, src, tgt, article, text):
    import mimetools
    from datetime import datetime
    import httplib2
    HTTP = httplib2.Http()
    BASE_URL = str(ServerlandHost.objects.get(shortname='remote').url)
    contents = {'token': str(token),
                'shortname': str(request_id),
                'worker': str(worker),
                'source_language': str(src),
                'target_language': str(tgt)}

    crlf = '\r\n'
    boundary = '-----' + mimetools.choose_boundary() + '-----'
    body = []
    for (key, value) in contents.items():
        body.append ('--' + boundary)
        body.append('Content-Disposition: form-data; name="%s"' % key)
        body.append('')
        body.append(value)
    body.append ('--' + boundary)
    body.append ('Content-Disposition: form-data; ' +
                  'name="source_text"; ' +
                  'filename="%s"' % article)
    body.append('Content-Type: text/plain; charset="UTF-8"')
    body.append('')
    body.extend(text.split('\n'))
    body.append ('--' + boundary)
    body.append('')
    body = (crlf.join(body)).encode("utf-8")
    content_type = 'multipart/form-data; boundary=%s' % boundary
    header = {'Content-Type': content_type, 'Content-Length': str(len(body))}

    response = HTTP.request(BASE_URL + 'requests/',
                            method='POST', body=body, headers=header)

    print 'create new request:'
    print 'response status:', response[0].status
    if response[0].status == 201:
        print 'response (json):', json.loads(response[1])
    else:
        print response[0].reason

    return request_id
