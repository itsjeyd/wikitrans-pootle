from datetime import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.forms.formsets import formset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from wt_articles.models import TranslatedArticle
from wt_managing.forms import SentenceReviewForm
from wt_managing.models import FINISHED, ArticleReview, SentenceReview
from wt_managing.utils import user_compatible_translations


if "notification" in settings.INSTALLED_APPS:
    from notification import models as notification
else:
    notification = None

@login_required
def reviewable_article_list(
    request, template_name="wt_managing/reviewable_article_list.html"):
    articles = user_compatible_translations(request.user)

    return render_to_response(template_name, {
        "articles": articles,
    }, context_instance=RequestContext(request))

@login_required
def reviewable_sentence_list(
    request, template_name="wt_managing/reviewable_sentence_list.html"):

    articles = user_compatible_translations(request.user)

    return render_to_response(template_name, {
        "articles": articles,
    }, context_instance=RequestContext(request))

@login_required
def review_translatedarticle(
    request, source, target, title, aid, form_class=SentenceReviewForm,
    template_name="wt_managing/translate_form.html"):
    """
    aid in this context is the translated article id
    """
    ta_set = TranslatedArticle.objects.filter(id=aid)
    if len(ta_set) < 1:
        return render_to_response(template_name,
                                  {"no_match": True},
                                  context_instance=RequestContext(request))

    article = ta_set[0]
    ts_list = article.sentences.all()
    TranslatedSentenceSet = formset_factory(form_class, extra=0)

    if request.method == "POST":
        formset = TranslatedSentenceSet(request.POST, request.FILES)
        if formset.is_valid():
            articlereview_id = formset.forms[0]. \
                               cleaned_data['articlereview']
            articlereview, created = ArticleReview.objects.get_or_create(
                id=articlereview_id)
            for form, trans_sent in zip(formset.forms, ts_list):
                accepted = form.cleaned_data['accepted']
                segment_id = form.cleaned_data['segment_id']
                print 'JD acc : %s' % accepted
                print 'JD seg : %s' % segment_id
                print 'JD aid : %s' % articlereview
                sent_review = SentenceReview(translated_sentence=trans_sent,
                                             articlereview=articlereview,
                                             accepted=accepted,
                                             review_date=datetime.now(),
                                             segment_id=segment_id,
                                             status=FINISHED)
                sent_review.save()
        return HttpResponseRedirect(reverse(reviewable_article_list))
    else:
        art_review = ArticleReview()
        art_review.translated_by = request.user.username
        sr_list = art_review.bootstrap(article)
        initial_ts_set = [{'translated_sentence': s,
                           'articlereview': s.articlereview.id,
                           'segment_id': s.segment_id} for s in sr_list]
        print initial_ts_set
        formset = TranslatedSentenceSet(initial=initial_ts_set)

    # Change label to show sentence
    for form, trans_sent in zip(formset.forms, ts_list):
        form.fields['accepted'].label = trans_sent.text

    return render_to_response(template_name, {
        "formset": formset,
        "title": article.title,
    }, context_instance=RequestContext(request))
