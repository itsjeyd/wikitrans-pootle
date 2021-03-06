from datetime import datetime
from django.core.management.base import NoArgsCommand
from wikipydia import query_text_rendered
from wt_articles.models import ArticleOfInterest
from wt_articles.models import SourceArticle

class Command(NoArgsCommand):
    help = "Updates the texts for wikipedia articles of interest"

    requires_model_validation = False

    def handle_noargs(self, **options):
        articles_of_interest = ArticleOfInterest.objects.all()
        for article in articles_of_interest:
            # don't import articles we already have
            if SourceArticle.objects.filter(title__exact='%s' % article.title,
                                            language=article.title_language):
                continue
            article_dict = query_text_rendered(
                article.title,
                language=article.title_language.code)
            try:
                source_article = SourceArticle(
                    title=article.title,
                    language=article.title_language,
                    source_text=article_dict['html'],
                    timestamp=datetime.now(),
                    doc_id=article_dict['revid']
                    )
                source_article.save()
            except Exception as e:
                print "Looks like we have an exception of type %s" % type(e)
                print "Exception args:", e.args
                try:
                    source_article.delete()
                except:
                    pass
