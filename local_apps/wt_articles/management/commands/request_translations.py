from wt_translation.models import send_translation_requests

class Command(NoArgsCommand):
    help = "Initiates translation requests for every untranslated article request."

    def handle_noargs(self, **options):
        send_translation_requests()
