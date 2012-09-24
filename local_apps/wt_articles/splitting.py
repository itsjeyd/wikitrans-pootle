#!/usr/bin/env python


from wt_languages.models import LANGUAGE_CHOICES

import re
import nltk.data

def determine_splitter(language):
    if language == 'ur':
        return urdu_split_sentences

    for desc_pair in LANGUAGE_CHOICES:
        if desc_pair[0] == language:
            tokenizer = 'tokenizers/punkt/%s.pickle' % (desc_pair[1].lower())
            break
    try:
        # TODO: Can we save multiple tokenizers in memory to speed up
        # the tokenization process?
        tokenizer = nltk.data.load(tokenizer)
        return tokenizer.tokenize
    except:
        raise AttributeError(
            '%s not supported by sentence splitters' % (language))

def urdu_split_sentences(text):
    """
    This function is a python implementation of Danish Munir's
    perl urdu-segmenter.
    """
    dash = u'\u06D4' # arabic full stop
    question = u'\u061F'
    ellipsis = u'\u2026'
    bullet = u'\u2022'
    carriage_return = u'\u000D'
    space = u'\u0020'
    full_stop = u'\u002e'

    text = text.replace('\r','')
    text = text.replace('\n','\n\n')
    reg_bullet = u'\s*%s\s*' % bullet
    text = re.sub(reg_bullet, '\n\n\n\n\n', text)

    text = text.replace('\t* +\t*$', ' ')

    reg_cr = u'[\n%s][ ]+[\n%s]' % (carriage_return, carriage_return)
    text = re.sub(reg_cr, '\n\n', text)

    reg_space = u'^[\t%s]+$' % space
    text = re.sub(reg_space, '\n\n', text)

    text = text.replace('|','')
    #/(\n{2,}|!|\x{061f}|\x{06D4}|\x{2022}|\x{000d}       |\s{2,}|\x{2026}|\x{002e})/
    # '\n{2,}|!|question|dash    |bullet  |carriage_return|\s{2,}|ellipsis|full_stop'
    regex = u'(\n{2,}|!|%s|%s|%s|%s|\s{2,}|%s|\%s)' % (
        question, dash, bullet, carriage_return, ellipsis, full_stop)
    punctuation = re.compile(regex)
    sentences = punctuation.split(text)

    new_string = ''
    segment_id = 1
    follow_up_punctuation = re.compile('[\n%s%s]' % (carriage_return, bullet))
    i = 0
    new_sentences = []
    while i < len(sentences):
        sent = sentences[i]
        sent = sent.strip()  # remove whitespace
        if len(sent) < 1:    # skip empty lines
            i = i+2
            continue
        new_string = new_string + sent
        # check punctuation in following sentence
        # if not newline, carriage_return or bullet, print it
        next_sent = sentences[i+1]
        if not follow_up_punctuation.match(next_sent):
            new_string = new_string + next_sent
        new_sentences.append(new_string + '\n')
        segment_id = segment_id + 1
        i = i + 2
    return new_sentences
