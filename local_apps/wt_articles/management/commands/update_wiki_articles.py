from datetime import datetime
from django.core.management.base import NoArgsCommand
from wikipydia import query_text_rendered
from wt_articles.models import ArticleOfInterest
from wt_articles.models import SourceArticle
from wt_articles.models import TranslationRequest
from wt_articles import DEFAULT_TRANNY

class Command(NoArgsCommand):
    help = "Updates the texts for wikipedia articles of interest"

    requires_model_validation = False

    def handle_noargs(self, **options):
        articles_of_interest = ArticleOfInterest.objects.all()
        for article in articles_of_interest:
            article_dict = query_text_rendered(article.title,
                                               language=article.title_language.code)
            # don't import articles we already have
            # if SourceArticle.objects.filter(doc_id__exact='%s' % article_dict['revid'],
            #                                 language=article.title_language):
            if SourceArticle.objects.filter(title__exact='%s' % article.title,
                                            language=article.title_language):
                continue
            try:
                source_article = SourceArticle(title=article.title,
                                               language=article.title_language,
                                               source_text=article_dict['html'],
                                               timestamp=datetime.now(),
                                               doc_id=article_dict['revid'])
                source_article.save()
            except Exception as e:
                print "Looks like we have an exception of type %s" % type(e)
                print "Exception args:", e.args
                try:
                    source_article.delete()
                except:
                    pass
