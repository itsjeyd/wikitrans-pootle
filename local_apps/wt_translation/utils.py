import pycountry
import uuid
from BeautifulSoup import BeautifulStoneSoup
from pootle_language.models import Language

def get_iso639_2(language):
    """
    Gets the iso-639-2 language format.
    """
    # TODO: Need to handle the case where a language isn't valid.
    language_length = len(language)

    if language_length == 2:
        return pycountry.languages.get(alpha2=language).bibliographic
    elif language_length == 3:
        return language
    else:
        # TODO: Add exception handling if the language locale doesn't exist
        return ''

def generate_request_id():
    return uuid.uuid1().hex

def clean_string(input):
    return BeautifulStoneSoup(
        input, convertEntities=BeautifulStoneSoup.ALL_ENTITIES
        ).contents[0]

def generate_request_body(boundary, contents, source_file_id, sentences):
    body = []
    for key, value in contents.items():
        body.append('--' + boundary)
        body.append('Content-Disposition: form-data; name="%s"' % key)
        body.append('')
        body.append(value)
    body.append('--' + boundary)
    body.append('Content-Disposition: form-data; ' +
                'name="source_text"; ' +
                'filename="%s"' % source_file_id)
    body.append('Content-Type: text/plain; charset="UTF-8"')
    body.append('')
    body.extend(sentences)
    body.append('--' + boundary)
    body.append('')
    crlf = '\r\n'
    return (crlf.join(body)).encode("utf-8")

def generate_request_header(boundary, body):
    content_type = 'multipart/form-data; boundary=%s' % boundary
    return {'Content-Type': content_type, 'Content-Length': str(len(body))}
