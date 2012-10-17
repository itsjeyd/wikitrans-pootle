from django.core.management.base import NoArgsCommand

from wt_translation.models import ServerlandConfigError
from wt_translation.models import ServerlandHost
from wt_translation.models import UndefinedTranslator
from wt_translation.models import UnsupportedLanguagePair


class Command(NoArgsCommand):
    help = "Looks for completed translation requests from all " \
           "Serverland hosts and updates their corresponding .po files."

    def handle_error(self, host, error):
        print "An error occurred with Serverland host '%s' (%s):" % \
              (host.shortname, host.url)
        print error

    def handle_noargs(self, **options):
        # Fetch all of the hosts
        hosts = ServerlandHost.objects.all()

        for host in hosts:
            try:
                host.fetch_translations()
            except UnsupportedLanguagePair as error:
                self.handle_error(host, error)
            except UndefinedTranslator as error:
                self.handle_error(host, error)
            except ServerlandConfigError as error:
                self.handle_error(host, error)
            except Exception as error:
                self.handle_error(host, error)
