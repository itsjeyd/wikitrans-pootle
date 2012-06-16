from django.core.management.base import NoArgsCommand
from wt_translation import STATUS_FINISHED
from wt_translation.models import ServerlandHost
from wt_translation.models import TranslationRequest

class Command(NoArgsCommand):
    help = "Deletes finished translation requests from server"

    def handle_noargs(self, **options):
        finished_requests = TranslationRequest.objects.filter(
            status=STATUS_FINISHED
            )
        host = ServerlandHost.objects.get(id=1)
        for request in finished_requests:
            print request
            host.delete_request(request.external_id)
