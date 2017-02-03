Installation
============

Users
^^^^^

1. Install requirements::

    sudo apt-get install wget git python python-virtualenv \
        python-dev python3-dev python3-pip

2. Configure your git credentials::

    git config --global user.name "Your Name"
    git config --global user.email "you@example.com"

3. Download git-repo::

    wget https://storage.googleapis.com/git-repo-downloads/repo
    chmod a+x ./repo

4. Get manifest files::

    python2 ./repo init -u https://github.com/uniflex/manifests.git

5. Configure user-only manifest file::

    python2 ./repo init -m user.xml

6. Get all repositories::

    # to get all repositories
    python2 ./repo sync
    # set master branch for all repos
    python2 ./repo forall -c 'git checkout master'
    # to check status of all repositories
    python2 ./repo status
    # to pull all repositories at once:
    python2 ./repo forall -c 'git pull --rebase'


Developers
^^^^^^^^^^

1. Create an account at our gitlab -> Go to: https://github.com/

2. Upload your public key into you account settings.

3. Install requirements::

    sudo apt-get install wget git python python-virtualenv \
        python-dev python3-dev python3-pip

4. Configure your git credentials::

    git config --global user.name "Your Name"
    git config --global user.email "you@example.com"

5. Download git-repo::

    wget https://storage.googleapis.com/git-repo-downloads/repo
    chmod a+x ./repo

5. Get manifest files::

    python2 ./repo init -u ssh://git@github.com/uniflex/manifests.git

6. Get all repositories::

    # to get all repositories
    python2 ./repo sync
    # set master branch for all repos
    python2 ./repo forall -c 'git checkout master'
    # to check status of all repositories
    python2 ./repo status
    # to pull all repositories at once:
    python2 ./repo forall -c 'git pull --rebase'


Installation
^^^^^^^^^^^^

1. Create virtual environment::

    virtualenv -p /usr/bin/python3 ./dev

2. Activate virtual environment::

    source ./dev/bin/activate

3. Install all dependencies (if all needed)::

    pip3 install -U -r ./.repo/manifests/requirements.txt

4. Deactivate virtual environment (if you need to exit)::

    deactivate

