Complex
================
A clone of [Simple](http://github.com/orf/simple).

About
============
The point of Simple is to be simple. This blog, on the other hand, is not.

Installation
============
Its quite simple. Go download Python 2.7+, Flask, Sqlalchemy and flask-sqlalchemy and you are good to go.
To create a settings file run create_config.py and enter some details, then run simple.py.

Deployment
============
Deploying Simple is easy. Simply clone this repo (or your own) and install [Gunicorn](http://gunicorn.org/).
Then cd to the directory containing simple.py and run the following command:
``gunicorn -w 4 simple:app``
This will start 4 gunicorn workers serving Simple. You can then use nginx or apache to forward requests to Gunicorn.

Example
============
You can see my blog running this software [here](http://tomforb.es/simple).

Screenshots
===========
![Admin](http://i.imgur.com/vWfOs.png)
![Draft](http://i.imgur.com/T9BX4.png)
![Live](http://i.imgur.com/WWDK4.png)