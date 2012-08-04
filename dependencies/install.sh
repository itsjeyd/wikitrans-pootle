#! /bin/bash

# apt-get
sudo apt-get install translate-toolkit
sudo apt-get install python-protobuf
sudo apt-get install python-yaml
sudo apt-get install libxslt-dev
sudo apt-get install libevent-dev

# Set up easy_install and pip
sudo apt-get install build-essential
sudo apt-get install python-setuptools
sudo apt-get install python-dev

sudo easy_install pip
sudo pip install --upgrade pip

# pip
sudo pip install -I -r requirements.txt

# Configure nltk
python nltk_config.py
