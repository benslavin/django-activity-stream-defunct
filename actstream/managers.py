from django.db.models.query import QuerySet
from django.db.models import Manager
from django.db import connection
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.conf import settings
from django.db import models

from actstream.genericforeignkey import * ## Not sure why this exists in two locations