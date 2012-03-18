#! /bin/bash

# Install easy_install and pip
sudo apt-get install python-setuptools python-dev build-essential
sudo easy_install pip
sudo pip install --upgrade pip

sudo apt-get install translate-toolkit
sudo apt-get install python-protobuf

# Install django
sudo pip install django

# Install dependencies from requirements.txt
sudo apt-get install libyaml-0-2
sudo pip install -I pyyaml

sudo apt-get install libxml2-dev
sudo apt-get install libxslt-dev
sudo pip install lxml

sudo apt-get install libevent-dev
sudo pip install -I -r requirements.txt

# Configure nltk
python nltk_config.py
