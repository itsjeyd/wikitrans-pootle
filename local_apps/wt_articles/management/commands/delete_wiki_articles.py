from django.core.management.base import NoArgsCommand

from wt_articles.models import SourceArticle


class Command(NoArgsCommand):
    help = "Delete all articles"

    requires_model_validation = False

    def handle_noargs(self, **options):
        articles_of_interest = SourceArticle.objects.all()
        for article in articles_of_interest:
            article.delete()
