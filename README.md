# Documentation

## Introduction
WikiTrans is an open-source machine translation project that is
intended for use with the Wikipedia community. Using Pootle as a
platform, users are able to request translations of Wikipedia articles
into various languages. The user community can review and post-edit
machine translations before submitting the new article to Wikipedia.
Eventually, these post-edits will be used to update the MT systems.

## Dependencies
As described below, an installation script can be used to
automatically install all dependencies listed in this section.

### apt-get
Some of WT's dependencies can be installed using `apt-get`. They
include:

- `translate-toolkit`, version 1.9
- `python-protobuf`
- `libyaml-0-2`
- `libxml2-dev`
- `libxslt-dev`
- `libevent-dev`

Additionally, in order to be able to `easy_install` pip and use that
for the remaining dependencies, the following packages need to be
installed:

- `build-essential`
- `python-dev`
- `python-setuptools`

### pip
All other dependencies of WT should be installed using `pip`:

- `django`, version 1.3.1
- `pyyaml`
- `lxml`
- `simplejson`
- `django-uni-form`
- `wikipydia`
- `goopytrans`
- `nltk`, version 2.0b7
- `polib`, version 0.5.3
- `BeautifulSoup`
- `apyrtium`
- `pycountry`

## Installation
1. Get code:

       <pre>$ git clone https://github.com/itsjeyd/wikitrans-pootle.git</pre>

2. Enter project directory:

       <pre>$ cd wikitrans-pootle</pre>

3. Run installation script:

       <pre>$ ./dependencies/install.sh</pre>

4. Start the server:

       <pre>$ ./PootleServer</pre>

5. In your browser, access the following URL:

       <pre>http://localhost:8080/wikitrans</pre>

   When doing this for the first time, this will initialize the
   database and populate it with languages supported by Pootle;
   additionally, a superuser will be created (user name: `admin`,
   password: `admin`).

   After initialization, you will be redirected to the main page of
   WikiTrans:

   ![WT main page](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/main-page.png)

6. Set up MT Serverland:

       <pre>
       $ python manage.py shell
       ...
       &gt;&gt;&gt; execfile('tests/serverland_init.py')
       </pre>


## Usage
N.B.: The shell commands listed throughout this section consistently
assume you are in the root directory of your WT installation; unless
you cloned the project into a custom folder or have renamed the folder
since you cloned it, the name of this directory should be
`wikitrans-pootle`.

### Logging in
Clicking the "Login" button on the main page brings up the login form
for WT:

![WT login](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/login.png)

You can use the superuser credentials created during the
initialization step to log in:

- Username: `admin`
- Password: `admin`

After successful login, you will be taken to your "Dashboard":

![WT dashboard](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/dashboard.png)

### Requesting Articles
From your dashboard, navigate to the Articles view by clicking on the
"Articles" tab. On the left hand side you will see a list of all
Wikipedia articles that have been imported into the system; if you are
doing this for the first time, this list will of course be empty. The
form on the right hand side can be used to request additional
Wikipedia articles you would like to translate (or make available to
your end users for translating):

![WT no-articles](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/no-articles.png)

To request an article, enter its full title in the "Title" field.
Then, from the drop-down menu next to "Title language", choose the
language in which the article is written, and click "Submit Query".

![WT request-article](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/request-article.png)

Note that doing this will not cause the article to be imported right
away. Instead, WikiTrans provides a custom command that takes care of
importing requested articles and making them available to registered
users:

    $ python manage.py update_wiki_articles


This command can be run manually by the administrator or automatically
at specific intervals, e.g. by scheduling it as a cron job.

After running the command, the Articles view lists the newly imported
article(s):

![WT articles](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/articles.png)

### Viewing and Editing Articles
As soon as a newly requested article has been imported into the system
and shows up in the list of articles, you can start working with it.

You can access the content of a specific article by clicking its name
in the listing:

![WT article](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/article.png)

When importing articles, WT tries its best to preserve their general
structure and formatting. If you do spot a mistake in an article, or
if you want to add or remove some parts from the original text before
translating it, you can click on "Fix Article" to bring up an editing
interface for that article:

![WT fix-article](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/fix-article.png)

There are only two things you need to keep in mind when editing an
article:

1. Each sentence needs to be on a separate line.
2. Paragraphs are separated using single blank lines.

Please note that any changes you decide to make to an article need to
be saved *before* requesting translations for it. Making changes later
on will not result in any errors, but they will not be incorporated
into the source text that is displayed in the interface for editing
translations.

### Creating Projects
To be able to request translations for an article, you first have to
create a project for it. You can do this simply by clicking on the
"Create new project" link next to the article. When you are done, the
article list should look like this:

![WT project-created](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/project-created.png)

Additionally, the system needs to know which target language(s) you
would like to work on for a given article. Adding one or more
languages to a project works like this:

1. Expand the "Target Language" drop-down and click "Add Language":

   ![WT add-language](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/add-language.png)

   This will take you to a page showing a list of available languages
   to choose from.

2. Hold down the Ctrl key and mark (i.e., left-click) all languages
   you would like to add to the project:

   ![WT add-language-list](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/add-language-list.png)

   Note that if you only want to add a single language, there is no
   need to hold down the Ctrl key.

3. When you are done, click "Submit Changes". This will take you back
   to the Articles view.

### Accessing projects
After adding some languages to a project, you can access it by
clicking on its name (e.g. "de:Hafenbecken") in the article list:

![WT project](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/project.png)

The project view lists all target languages selected for a given
source article and project.

### Requesting Translations
On the project page for a given source article, you can request a
translation into a specific target language like this:

1. Expand the corresponding drop-down menu and choose one of the
   workers listed:

   ![WT choose-worker](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/choose-worker.png)

2. Click "Go!"

If WT lists different sets workers for different target languages,
this is because not every worker can handle every single pair of
languages available through Pootle.

#### Forwarding requests
Since WT depends on external MT services for translating Wikipedia
articles, each translation request made by you or one of your end
users needs to be forwarded to a translation host. For this purpose,
the following command can be used:

    $ python manage.py request_translations


#### Fetching translations
To import translation results from the translation host into WT, use
the following command:

    $ python manage.py fetch_translations


#### Deleting requests (on the MT host)
While `request_translations` and `fetch_translations` are the most
important commands for dealing with translation requests and therefore
need to be run most often, there is another command you should run on
a somewhat regular basis:

    $ python manage.py delete_finished_requests


For each finished request in the system, WT tells the translation host
to delete that request. A request is considered to be "finished" if
the translation produced for it by the translation host has been
imported into WT successfully.

### Viewing and Editing Translations
For each of the target languages chosen for a given article, WT
provides an overview page showing progress information. This overview
page can be accessed from the project page by clicking the name of the
language on the project page.

![WT translation-overview](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/translation-overview.png)

Clicking on "article.po" takes you to the editing interface for a
specific source article and translation, which looks like this:

![WT edit-translation](https://raw.github.com/itsjeyd/wikitrans-pootle/master/screenshots/edit-translation.png)

Individual sentences can be edited in place; clicking "Submit" saves
the changes.

### Deleting Projects
Individual projects can be deleted simply by clicking the
corresponding "Delete" button in the article listing.
