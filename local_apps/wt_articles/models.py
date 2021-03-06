import re

import polib

from datetime import datetime
from urllib import quote_plus

from BeautifulSoup import BeautifulSoup
from django.db import models
from django.conf import settings
from django.utils.encoding import iri_to_uri
from django.utils.translation import ugettext_lazy as _

from pootle_language.models import Language
from pootle_project.models import Project

from wt_articles import TRANSLATION_STATUSES
from wt_articles.splitting import determine_splitter
from wt_translation.models import MachineTranslator



if "notification" in settings.INSTALLED_APPS:
    from notification import models as notification
else:
    notification = None


class ArticleOfInterest(models.Model):
    title = models.CharField(_('Title'), max_length=255)
    title_language = models.ForeignKey(Language, db_index=True)

    def __unicode__(self):
        return u"%s :: %s" % (self.title, self.title_language)


class SourceArticle(models.Model):
    title = models.CharField(_('Title'), max_length=255)
    language = models.ForeignKey(Language, db_index=True)
    timestamp = models.DateTimeField(_('Import Date'), default=datetime.now())
    doc_id = models.CharField(_('Document ID'), max_length=512)
    source_text = models.TextField(_('Source Text'))
    sentences_processed = models.BooleanField(_('Sentences Processed',
                                                default=False))
    pootle_project = models.ForeignKey(Project, null=True)

    def __unicode__(self):
        return u"%s :: %s :: %s" % (self.id, self.doc_id, self.title)

    def save(self, manually_splitting=False, source_sentences=()):
        if not self.sentences_processed and not manually_splitting:
            soup = BeautifulSoup(self.source_text)
            sentence_splitter = determine_splitter(self.language.code)
            super(SourceArticle, self).save()

            segment_id = 0
            for tag in soup.findAll(re.compile('^[ph]')):
                if re.match('p', tag.name):
                    p_text = ''.join([x.string for x in tag.findAll(text=True)
                                      if not re.match('[\[\]\\d]+$',
                                                      x.string)])
                    sentences = sentence_splitter(p_text.strip())
                    for sentence in sentences:
                        sentence = sentence.replace("&#160;", " ")
                        src_sent = SourceSentence(article=self,
                                                  text=sentence,
                                                  segment_id=segment_id,
                                                  is_heading=False,
                                                  heading_level=0)
                        segment_id += 1
                        src_sent.save()
                    src_sent.end_of_paragraph = True
                    src_sent.save()

                elif re.match('h\d', tag.name):
                    headline = tag.findAll(attrs={'class': 'mw-headline'})
                    if headline:
                        content = headline[0].string
                    else:
                        content = tag.string
                    if content.lower() == 'weblinks':
                        break
                    src_sent = SourceSentence(article=self,
                                              text=content,
                                              segment_id=segment_id,
                                              is_heading=True,
                                              heading_level=int(tag.name[-1]))
                    src_sent.save()
                    segment_id += 1

            self.sentences_processed = True

        else:
            for sentence in source_sentences:
                sentence.save()

        super(SourceArticle, self).save()

    def delete(self):
        # First, try to delete the associated pootle project.
        try:
            self.delete_pootle_project(delete_local=True)
        except Exception:
            # No need to do anything.
            pass

        # TODO: Do we also need to delete all of the translations?

        # Then delete the article.
        super(SourceArticle, self).delete()

    def delete_sentences(self):
        for sentence in self.sourcesentence_set.all():
            SourceSentence.delete(sentence)

    def get_absolute_url(self):
        url = ('/wikitrans/articles/source/%s/%s/%s' %
               (self.language.code,
                quote_plus(self.title.encode('utf-8')),
                self.id))
        return iri_to_uri(url)

    def get_relative_url(self, lang_string=None):
        if lang_string == None:
            lang_string = self.language.code
        url = '%s/%s/%s' % (lang_string,
                            quote_plus(self.title.encode('utf-8')),
                            self.id)
        return iri_to_uri(url)

    def get_fix_url(self):
        url = '/wikitrans/articles/fix/%s' % self.id

        return iri_to_uri(url)

    def get_export_po_url(self):
        url = '/articles/source/export/po/%s' % self.id

        return iri_to_uri(url)

    def sentences_to_po(self):
        po = polib.POFile()
        # Create the header
        po.metadata = {
            'Source-Article': self.doc_id,
            'Article-Title': self.title,
            'Article-Language': self.language.code,
            'Project-Id-Version': '1.0',
            'Report-Msgid-Bugs-To': 'eisele@dfki.de',
            'POT-Creation-Date': datetime.utcnow().isoformat(),
            'Last-Translator': 'admin',
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Content-Transfer-Encoding': '8bit',
        }

        # Export the title
        po_title = polib.POEntry(
            tcomment = "Title",
            msgid = self.title
        )
        po.append(po_title)

        # Export the sentences
        for sentence in self.sourcesentence_set.order_by('segment_id'):
            po_entry = polib.POEntry(
                occurrences = [('segment_id', sentence.segment_id)],
                tcomment = "sentence",  # TODO: Check to see if it's a
                                        # sentence or a header
                msgid = sentence.text
            )

            po.append(po_entry)

        return po

    def sentences_to_lines(self):
        lines = []
        for sentence in self.sourcesentence_set.order_by('segment_id'):
            text = sentence.text
            if sentence.end_of_paragraph:
                text += "\n"
            lines.append(text)

        return "\n".join(lines).strip()
    def lines_to_sentences(self, lines):
        segment_id = 0
        source_sentences = []

        # Get each sentence; mark the last sentence of each paragraph
        sentences = lines.split("\n")
        s_count = len(sentences)
        for i in range(0, s_count):
            if i > 0 and len(sentences[i].strip()) == 0:
                source_sentences[segment_id-1].end_of_paragraph = True
            else:
                src_sent = SourceSentence(article=self,
                                          text=sentences[i].strip(),
                                          segment_id=segment_id)

                source_sentences.append(src_sent)
                segment_id += 1

        return source_sentences

    def get_project_name(self):
        return u"%s:%s" % (self.language.code, self.title)

    def get_project_code(self):
        return u"%s_%s" % (self.language.code, self.title.replace(" ", "_"))

    def pootle_project_exists(self):
        """
        Determines if a Pootle project already exists for this article
        """
        return Project.objects.filter(code = self.get_project_code()).exists()

    def delete_pootle_project(self, delete_local=False):
        '''
        Deletes the associated Pootle project.
        '''
        import os
        project = self.get_pootle_project()

        # Get the project's directory
        proj_abs_path = project.get_real_path()

        # Remove the project reference in the SourceArticle
        self.pootle_project = None
        self.save()

        # Delete the project
        project.delete()

        if delete_local and len(proj_abs_path) > 3:
            import shutil
            if os.path.exists(proj_abs_path):
                shutil.rmtree(proj_abs_path)

    def create_pootle_project(self):
        '''
        Creates a project to be used in Pootle. A templates language
        is created and a .pot template is generated from the
        SourceSentences in the article.
        '''
        import logging
        from django.utils.encoding import smart_str
        from pootle_app.models.signals import post_template_update


        # Fetch the source_language
        sl_set = Language.objects.filter(code = self.language.code)

        if len(sl_set) < 1:
            return False

        source_language = sl_set[0]

        # 1. Construct the project
        project = Project()
        project.fullname = u"%s:%s" % (self.language.code, self.title)
        project.code = project.fullname.replace(" ", "_").replace(":", "_")
        # PO filetype

        project.source_language = source_language
        # Save the project
        project.save()

        templates_language = Language.objects.get_by_natural_key('templates')

        # Check to see if the templates language exists. If not, add it.
        if len(project.translationproject_set.filter(
            language=templates_language)) == 0:
            project.add_language(templates_language)
            project.save()

        #code copied for wt_articles
        logging.debug ( "project saved")
        # 2. Export the article to .po and store in the templates
        # "translation project". This will be used to generate
        # translation requests for other languages.
        templates_project = project.get_template_translationproject()
        po = self.sentences_to_po()
        po_file_path = "%s/article.pot" % (templates_project.abs_real_path)

        oldstats = templates_project.getquickstats()

        # Write the file
        with open(po_file_path, 'w') as po_file:
            po_file.write(smart_str(po.__str__()))

        # Force the project to scan for changes.
        templates_project.scan_files()
        templates_project.update(conservative=False)

        # Log the changes
        newstats = templates_project.getquickstats()
        post_template_update.send(sender=templates_project,
                                  oldstats=oldstats,
                                  newstats=newstats)

        # Add a reference to the project in the SourceArticle
        self.pootle_project = project
        self.save()

        return project

    def get_pootle_project(self):
        """
        Gets a handle of the Pootle project, if it exists.
        """
        # First, check to see if the project is already bound to the
        # SourceArticle
        if self.pootle_project == None:
            # Otherwise, look it up
            queryset = Project.objects.filter(code = self.get_project_code())
            if not queryset.exists():
                raise Exception("Project does not exist!")

            # If it's found, save its reference to the SourceArticle
            self.pootle_project = queryset[0]
            self.save()

        return self.pootle_project

    def get_target_languages(self):
        """
        Gets the languages of the translation projects (excluding
        templates) under the corresponding Pootle project.
        """
        try:
            translation_projects = self.get_pootle_project().\
                                   translationproject_set.\
                                   exclude(language__code="templates")
            return Language.objects.filter(id__in=
                                           [tp.language.id for tp in
                                            translation_projects])
        except Exception:
            return []

    def add_target_languages(self, languages):
        try:
            pootle_project = self.get_pootle_project()
        except Exception:
            # Create the project if it doesn't exist
            pootle_project = self.create_pootle_project()

        for language in languages:
            pootle_project.add_language(language)

    def get_pootle_project_url(self):
        """
        Gets the url corresponding to the Pootle project.
        """
        url = '/wikitrans/projects/%s/' % self.get_project_code()

        return iri_to_uri(url)

    def get_pootle_project_language_url(self, language):
        """
        Gets the url corresponding to a Pootle TranslationProject (language).
        """
        url = '/%s/%s/' % (language.code, self.get_project_code())
        return iri_to_uri(url)

    def get_add_target_language_url(self):
        """
        Gets the url that allows the user to add additional target languages.
        """
        url = '/wikitrans/articles/translate/languages/add/%s' % self.id
        return iri_to_uri(url)

    def get_create_pootle_project_url(self):
        """
        Gets the url for the page which creates a new Pootle project
        out of a source article
        """
        url = '/wikitrans/articles/source/export/project/%s' % self.id
        return iri_to_uri(url)

    def get_delete_pootle_project_url(self):
        """
        Gets the url for the page which deletes the Pootle project
        associated with the source article.
        """
        url = '/wikitrans/articles/source/delete/project/%s' % self.id
        return iri_to_uri(url)

    def has_translation_request(self, target_language, translator):
        return self.translationrequest_set.filter(target_language=
                                                  target_language,
                                                  translator=
                                                  translator).exists()

    def create_translation_request(self, target_language, translator):
        # Try to create the translation request. An exception may be thrown.
        translation_request = TranslationRequest()
        translation_request.article = self
        translation_request.target_language = target_language
        translation_request.translator = translator

        translation_request.save()


class SourceSentence(models.Model):
    article = models.ForeignKey(SourceArticle)
    text = models.CharField(_('Sentence Text'), max_length=2048)
    segment_id = models.IntegerField(_('Segment ID'))
    end_of_paragraph = models.BooleanField(_('Paragraph closer'))
    is_heading = models.NullBooleanField(_('Heading'))
    heading_level = models.IntegerField(_('Heading Level'), null=True)

    class Meta:
        ordering = ('segment_id','article')

    def __unicode__(self):
        return u"%s :: %s :: %s" % (self.id, self.segment_id, self.text)

    def save(self):
        super(SourceSentence, self).save()


class TranslationRequest(models.Model):
    article = models.ForeignKey(SourceArticle)
    target_language = models.ForeignKey(Language, db_index=True)
    date = models.DateTimeField(_('Request Date'))
    translator = models.ForeignKey(MachineTranslator)
    status = models.CharField(_('Request Status'),
                              max_length=32,
                              choices=TRANSLATION_STATUSES)
    external_id = models.CharField(_('External Request ID'),
                                   max_length=32)

    def __unicode__(self):
        return u"%s: %s" % (self.target_language, self.article)

    def get_subset(self, request_status):
        """
        Retrieves all of the TranslationRequests that have a specific status
        """
        return TranslationRequest.objects.filter(status=request_status)

    def send_request(self):
        """
        Sends the translation request to the machine translator.
        """
        pass

    class Meta:
        unique_together = ("article", "target_language", "translator")


class TranslatedSentence(models.Model):
    segment_id = models.IntegerField(_('Segment ID'))
    source_sentence = models.ForeignKey(SourceSentence)
    text = models.CharField(_('Translated Text'), blank=True, max_length=2048)
    translated_by = models.CharField(_('Translated by'),
                                     blank=True,
                                     max_length=255)
    language = models.ForeignKey(Language, db_index=True)
    translation_date = models.DateTimeField(_('Import Date'))
    approved = models.BooleanField(_('Approved'), default=False)
    end_of_paragraph = models.BooleanField(_('Paragraph closer'))

    class Meta:
        ordering = ('segment_id',)

    def __unicode__(self):
        return u'%s' % (self.id)


class TranslatedArticle(models.Model):
    article = models.ForeignKey(SourceArticle)
    parent = models.ForeignKey('self', blank=True, null=True,
                               related_name='parent_set')
    title = models.CharField(_('Title'), max_length=255)
    timestamp = models.DateTimeField(_('Timestamp'))
    language = models.ForeignKey(Language, db_index=True)
    sentences = models.ManyToManyField(TranslatedSentence)
    approved = models.BooleanField(_('Approved'), default=False)

    def set_sentences(self, translated_sentences):
        source_sentences = self.article.sourcesentence_set.order_by(
            'segment_id')
        source_segment_ids = [s.segment_id for s in source_sentences]
        translated_segment_ids = [s.segment_id for s in translated_sentences]
        if len(source_segment_ids) != len(translated_segment_ids):
            raise ValueError(
                "Number of translated sentences doesn't match " \
                "number of source sentences")
        if source_segment_ids != translated_segment_ids:
            ValueError('Segment id lists do not match')
        translated_article_list = [ts.source_sentence.article for ts in \
                                       translated_sentences]
        if (len(translated_article_list) != 1 and
            translated_article_list[0] != self.article):
            raise ValueError('Not all translated sentences derive from the ' \
                                 'source article')
        for trans_sent in translated_sentences:
            self.sentences.add(trans_sent)

    def __unicode__(self):
        return u'%s :: %s' % (self.title, self.article)

    #@models.permalink
    def get_absolute_url(self):
        source_lang = self.article.language.code
        target_lang = self.language.code
        lang_pair = "%s-%s" % (source_lang, target_lang)
        url = ('/articles/translated/%s/%s/%s' %
               (lang_pair,
                quote_plus(self.title.encode('utf-8')),
                self.id))
        return iri_to_uri(url)

    def get_relative_url(self):
        source_lang = self.article.language.code
        target_lang = self.language.code
        lang_pair = "%s-%s" % (source_lang, target_lang)
        url = '%s/%s/%s' % (lang_pair,
                            quote_plus(self.title.encode('utf-8')),
                            self.id)
        return iri_to_uri(url)


class FeaturedTranslation(models.Model):
    featured_date = models.DateTimeField(_('Featured Date'))
    article = models.ForeignKey(TranslatedArticle)

    class Meta:
        ordering = ('-featured_date',)

    def __unicode__(self):
        return u'%s :: %s' % (self.featured_date, self.article.title)

def latest_featured_article():
    featured_translations = FeaturedTranslation.objects.all()[0:]
    if len(featured_translations) > 0:
        return featured_translations[0]
    else:
        return None
