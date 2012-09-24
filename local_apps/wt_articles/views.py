from datetime import datetime
from urllib import unquote_plus

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from wikipydia import query_text_rendered

from wt_articles.forms import AddTargetLanguagesForm
from wt_articles.forms import ArticleRequestForm
from wt_articles.forms import DummyFixArticleForm
from wt_articles.forms import TranslatedSentenceMappingForm
from wt_articles.models import ArticleOfInterest
from wt_articles.models import latest_featured_article
from wt_articles.models import SourceArticle
from wt_articles.models import TranslatedArticle
from wt_articles.models import TranslatedSentence
from wt_articles.utils import all_source_articles
from wt_articles.utils import sentences_as_html
from wt_articles.utils import sentences_as_html_span
from wt_articles.utils import target_pairs_by_user
from wt_articles.utils import user_compatible_articles
from wt_articles.utils import user_compatible_source_articles
from wt_articles.utils import user_compatible_target_articles


if "notification" in settings.INSTALLED_APPS:
    from notification import models as notification
else:
    notification = None


def landing(request, template_name="wt_articles/landing.html"):
    featured_translation = latest_featured_article()
    featured_text = u'No translations are featured'
    if featured_translation != None:
        featured_text = sentences_as_html(
            featured_translation.article.sentences.all())

    recent_translations = TranslatedArticle.objects.order_by('-timestamp')[:5]

    return render_to_response(template_name, {
        "featured_translation": featured_text,
        "recent_translations": recent_translations,
    }, context_instance=RequestContext(request))


def show_source(request, title, source, aid=None,
                template_name="wt_articles/show_article.html"):
    title = unquote_plus(title)

    if aid != None:
        sa_set = SourceArticle.objects.filter(id=aid)
    else:
        sa_set = SourceArticle.objects.filter(
            language=source, title=title).order_by('-timestamp')
    if len(sa_set) > 0:
        article_text = sentences_as_html_span(
            sa_set[0].sourcesentence_set.all())
    else:
        article_text = None

    return render_to_response(template_name, {
        "title": title,
        "article_text": article_text,
    }, context_instance=RequestContext(request))


def show_translated(request, title, source, target, aid=None,
                    template_name="wt_articles/show_article.html"):
    title = unquote_plus(title)
    if aid != None:
        ta_set = TranslatedArticle.objects.filter(id=aid)
    else:
        ta_set = TranslatedArticle.objects.filter(
            article__language=source,
            language=target,
            title=title).order_by('-timestamp')
    if len(ta_set) > 0:
        article_text = sentences_as_html(ta_set[0].sentences.all())
    else:
        article_text = None
    return render_to_response(template_name, {
        "title": title,
        "article_text": article_text,
    }, context_instance=RequestContext(request))


def article_search(request, template_name="wt_articles/article_list.html"):
    if request.method == "POST" and request.POST.has_key('search'):
        name = request.POST['search']
        articles = TranslatedArticle.objects.filter(title__icontains=name)
        print articles
    else:
        articles = []
    return render_to_response(template_name, {
        'articles': articles,
    }, context_instance=RequestContext(request))


@login_required(login_url='/wikitrans/accounts/login/')
def article_list(request, template_name="wt_articles/article_list.html"):
    # TODO: Request user-compatible articles; for now, we show all
    # articles, since we are merging with Pootle. articles =
    # user_compatible_articles(request.user)
    articles = all_source_articles()

    content_dict = { "articles": articles, }
    content_dict.update(request_article(request))

    return render_to_response(template_name, content_dict,
                              context_instance=RequestContext(request))


@login_required
def fix_article_list(request,
                     template_name="wt_articles/fix_article_list.html"):
    articles = user_compatible_articles(request.user)

    return render_to_response(template_name, {
        "articles": articles,
    }, context_instance=RequestContext(request))


@login_required
def translatable_list(request,
                      template_name="wt_articles/article_list.html"):
    import copy
    user = request.user
    source_articles = user_compatible_source_articles(request.user)
    articles = []
    for src_art in source_articles:
        lang_pairs = target_pairs_by_user(user, src_art.language)
        for pair in lang_pairs:
            article = copy.deepcopy(src_art)
            article.target = pair[0]
            article.link = (u'/articles/translate/new/%s' %
                            (article.get_relative_url(pair[1])))
            articles.append(article)

    return render_to_response(template_name, {
        "articles": articles,
        "translatable": True,
    }, context_instance=RequestContext(request))


@login_required
def posteditable_list(request,
                      template_name="wt_articles/article_list.html"):
    import copy
    user = request.user
    target_articles = user_compatible_target_articles(request.user)
    articles = []
    for target_art in target_articles:
        lang_pairs = target_pairs_by_user(user, target_art.language)
        for pair in lang_pairs:
            article = copy.deepcopy(target_art)
            article.target = pair[0]
            article.link = (u'/articles/translate/postedit/%s' %
                            (article.get_relative_url()))
            articles.append(article)

    return render_to_response(template_name, {
        "articles": articles,
        "translatable": True,
    }, context_instance=RequestContext(request))


@login_required
def translate_from_scratch(request, source, target, title, aid,
                           template_name="wt_articles/translate_form.html"):
    """
    Loads a source article by provided article id (aid) and generates
    formsets to contain each sentence in the requested translation.
    """
    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        return render_to_response(template_name,
                                  {"no_match": True},
                                  context_instance=RequestContext(request))
    article = sa_set[0]
    ss_list = article.sourcesentence_set.all()
    TranslatedSentenceSet = formset_factory(TranslatedSentenceMappingForm,
                                            extra=0)

    if request.method == "POST":
        formset = TranslatedSentenceSet(request.POST, request.FILES)
        if formset.is_valid():
            ts_list = []
            trans_art = TranslatedArticle()
            for form in formset.forms:
                src_sent = form.cleaned_data['source_sentence']
                text = form.cleaned_data['text']
                trans_sent = TranslatedSentence(
                    segment_id=src_sent.segment_id,
                    source_sentence=src_sent,
                    text=text,
                    translated_by=request.user.username,
                    translation_date=datetime.now(),
                    language=target,
                    best=True,
                    end_of_paragraph=src_sent.end_of_paragraph)
                ts_list.append(trans_sent)
            trans_art.article = src_sent.article
            trans_art.title = src_sent.article.title
            trans_art.timestamp = datetime.now()
            trans_art.language = target
            trans_art.save()
            for trans_sent in ts_list:
                trans_sent.save()
            trans_art.sentences = ts_list
            trans_art.save()
            return HttpResponseRedirect(trans_art.get_absolute_url())
    else:
        initial_ss_set = [{'source_sentence': s} for s in ss_list]
        formset = TranslatedSentenceSet(initial=initial_ss_set)
    for form, sent in zip(formset.forms, ss_list):
        form.fields['text'].label = sent.text

    return render_to_response(template_name, {
        "formset": formset,
        "title": article.title,
    }, context_instance=RequestContext(request))


@login_required
def translate_post_edit(request, source, target, title, aid,
                        template_name="wt_articles/translate_form.html"):
    """
    Loads a translated article by its article id (aid) and generates
    formsets with the source article and translated sentence. It then
    generates a new translated article out of the input from the user
    """
    ta_set = TranslatedArticle.objects.filter(id=aid)
    if len(ta_set) < 1:
        return render_to_response(template_name,
                                  {"no_match": True},
                                  context_instance=RequestContext(request))
    translated_article = ta_set[0]
    ts_list = translated_article.sentences.all()
    ss_list = translated_article.article.sourcesentence_set.all()
    TranslatedSentenceSet = formset_factory(TranslatedSentenceMappingForm,
                                            extra=0)

    if request.method == "POST":
        formset = TranslatedSentenceSet(request.POST, request.FILES)
    else:
        initial_ts_set = [{'text': s.text} for s in ts_list]
        formset = TranslatedSentenceSet(initial=initial_ts_set)
    for form, sent in zip(formset.forms, ss_list):
        form.fields['text'].label = sent.text
        form.fields['text'].__dict__

    return render_to_response(template_name, {
        "formset": formset,
        "title": translated_article.title,
    }, context_instance=RequestContext(request))


@login_required
def fix_article(request, aid, form_class=DummyFixArticleForm,
                template_name="wt_articles/fix_article.html"):
    """
    aid in this context is the source article id
    """
    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        return render_to_response(template_name,
                                  {"no_match": True},
                                  context_instance=RequestContext(request))
    article = sa_set[0]

    if request.method == "POST":
        # fix_form = form_class(request.POST, instance=article)
        fix_form = DummyFixArticleForm(request.POST)

        if fix_form.is_valid():
            # TODO: Process the form.
            article.title = fix_form.cleaned_data['title']
            lines = fix_form.cleaned_data['sentences']

            # Convert the textarea of lines to SourceSentences
            sentences = article.lines_to_sentences(lines)

            # Delete the old sentences before saving the new ones
            article.delete_sentences()
            article.save(manually_splitting=True, source_sentences=sentences)

            return HttpResponseRedirect(article.get_absolute_url())
    else:
        # TODO: For some reason, FixArticleForm worked in the original
        # WikiTrans, but is no longer working when merged with Pootle.
        # fix_form = form_class(instance=article,
        # initial = {'sentences': article.sentences_to_lines()}
        dummy_fix_form = DummyFixArticleForm(initial=
                                             {'sentences':
                                                  article.sentences_to_lines(),
                                              'title': article.title})

    return render_to_response(template_name, {
        "article": article,
        "fix_form": dummy_fix_form
    }, context_instance=RequestContext(request))


@login_required
def request_article(request,
                    form_class=ArticleRequestForm,
                    template_name="wt_articles/request_form.html"):
    if request.method == "POST":
        article_request_form = form_class(request.POST)
        if article_request_form.is_valid():
            title = article_request_form.cleaned_data['title']
            title_language = article_request_form.cleaned_data['title_language']
            if not ArticleOfInterest.objects.filter(
                title__exact=title, title_language__exact=title_language):
                article_of_interest = article_request_form.save(commit=False)
                article_of_interest.date = datetime.now()
                article_of_interest.save()
                article_dict = query_text_rendered(
                    title, language=title_language.code)
                request_form = form_class()
                return {"article_requested": True,
                        "request_form": request_form}
    else:
        request_form = form_class()
        return {"article_requested": False,
                "request_form": request_form}


@login_required
def source_to_po(request, aid,
                 template_name="wt_articles/source_export_po.html"):
    """
    aid in this context is the source article id
    """
    from django.utils.encoding import smart_str

    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        return render_to_response(template_name,
                                  {"no_match": True},
                                  context_instance=RequestContext(request))

    article = sa_set[0]
    po = article.sentences_to_po()

    return render_to_response(template_name, {
        "po": smart_str( po ),
        "title": article.title
    }, context_instance=RequestContext(request))


@login_required
def delete_pootle_project(request, aid):
# TODO: Display notification on page that the project has been
# deleted.
    """
    Deletes a pootle Project by id (aid).
    """
    # Fetch the article

    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        pass
    else:
        article = sa_set[0]
        article.delete_pootle_project(delete_local=True)

    # Display the article list.
    return article_list(request)


@login_required
def create_pootle_project(request, aid):
# TODO: Display notification on page that the project has been
# created. def create_pootle_project(request, aid,
# template_name="wt_articles/source_export_project.html"):
    """
    Converts an article to a Pootle project by id (aid).
    """
    # Fetch the article

    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        pass
    else:
        article = sa_set[0]
        project = article.create_pootle_project()

    # Display the article list
    return article_list(request)


@login_required
def add_target_languages(request, aid,
                         template_name="wt_articles/add_target_languages.html"):
    """
    Adds one or more target language translations to a source article.
    """
    content_dict = {}

    # Fetch the article
    no_match = False

    sa_set = SourceArticle.objects.filter(id=aid)
    if len(sa_set) < 1:
        no_match = True
        content_dict['no_match'] = no_match
    else:
        article = sa_set[0]
        content_dict['article'] = article

        if request.method == "POST":
            target_language_form = AddTargetLanguagesForm(article, request.POST)

            if target_language_form.is_valid():
                languages = target_language_form.cleaned_data['languages']

                article.add_target_languages(languages)
                return HttpResponseRedirect('/wikitrans/articles/list')
        else:
            target_language_form = AddTargetLanguagesForm(article)

        content_dict['target_language_form'] = target_language_form
    return render_to_response(template_name, content_dict,
                              context_instance=RequestContext(request))
