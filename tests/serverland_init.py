from wt_translation.models import MachineTranslator, ServerlandHost

host = ServerlandHost()
host.shortname = "remote"
host.url = "http://www.dfki.de/mt-serverland/dashboard/api/xml/"
host.token = "4c4ab8e2"
host.description = "ServerLand host running on DFKI servers"
host.save()
