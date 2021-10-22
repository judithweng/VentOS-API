
# Mock PIRDS and PIRCS server

This Django website aims to simulate a patient on a ventilator.

Design specification for the [simulation are here](https://docs.google.com/document/d/1TWMuEWoQLA8TJQWGYQNGAeTDgZ9xA_z4yTwOkDA0pP0/edit) and for the [PIRCS/PIRDS endpoints here](https://docs.google.com/document/d/1TWMuEWoQLA8TJQWGYQNGAeTDgZ9xA_z4yTwOkDA0pP0/edit).

# Installing

This is a vanilla Django website which includes good support for running the site on your local machine.

Simply clone the repo, create a python "environment", install dependancies, create a superuser with these commands:

    cd [working folder]
    git clone [repo]
    cd [project folder]
    # create and activate venv
    python3 -m venv ventosapivenv
    source ventosapivenv/bin/activate
    # install dependancies and create superuser (follow prompts)
    pipenv install
    ./manage.py createsuperuser

Then to run a local server:

    ./manage.py runserver

This will make the admin visible here:

    http://127.0.0.1:8000/admin/main/

# Deployment

In order to run this application as a web service, for our own personal ease
and to reuse an existing site, we are currently only deploying the main module.

Erich is currently doing this by rsyncing files with server and vica versa:

    rsync -au /home/erich/ventos_api/main erich@drop1:/home/erich/accord1
    rsync -au erich@drop1:/home/erich/accord1/main /home/erich/ventos_api

Then a restart of the gunicorn and nginx service:

    /home/erich/accord1/restart.sh

The endpoints are visible at this temporary home:

    https://ventos.dev/ventos/3
    https://ventos.dev/ventos/control/
