from django.conf.urls.defaults import patterns, url

from wt_languages import views


urlpatterns = patterns('',
    # your language competancies
    url(r'^$', 'wt_languages.views.language_competancy_list',
        name="language_competancy_list"),

    # new competancy
    url(r'^new/$', 'wt_languages.views.language_competancy_new',
        name='language_competancy_new'),

    # edit competancy
    url(r'^edit/(\d+)/$', 'wt_languages.views.language_competancy_edit',
        name='language_competancy_edit'),

    #destory competancy
    url(r'^destroy/(\d+)/$',
        'wt_languages.views.language_competancy_destroy',
        name='language_competancy_destroy'),

)
