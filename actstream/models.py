from operator import or_
from django.db import models
from django.db.models import Q
from django.db.models.query import QuerySet
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.utils.timesince import timesince as timesince_
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import User
from django.conf import settings

from actstream.signals import action

class FollowManager(models.Manager):
    def stream_for_user(self, user):
        """
        Produces a QuerySet of most recent activities from subjects the user follows
        """
        follows = self.filter(user=user)
        qs = (Action.objects.stream_for_subject(follow.subject,user=user).filter(timestamp__gt=follow.started) for follow in follows)
        if follows.count():
            return reduce(or_, qs).order_by('-timestamp')
    
class Follow(models.Model):
    """
    Lets a user follow the activities of any specific subject
    """
    user = models.ForeignKey(User)
    
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField() 
    subject = generic.GenericForeignKey()
    started = models.DateTimeField(auto_now_add=True)
    
    objects = FollowManager()
    
    def __unicode__(self):
        return u'%s -> %s' % (self.user, self.subject)

class ActionManager(models.Manager):
    def stream_for_actor(self, actor, user=None):
        """
        Produces a QuerySet of most recent activities for any actor

        Jordan: eventually we do need to filter out public/private actions, but for now
                we'll just filter out private actions altogether.
        """
        
        return self.filter(
            actor_content_type = ContentType.objects.get_for_model(actor),
            actor_object_id = actor.pk,
        ).exclude(public=False).order_by('-timestamp')
        
    def stream_for_model(self, model):
        """
        Produces a QuerySet of most recent activities for any model
        """
        return self.filter(
            actor_content_type = ContentType.objects.get_for_model(model),
        ).order_by('-timestamp')
        
    def stream_for_subject(self, subject, user=None):
        """
        Produces a QuerySet of most recent activities for a subject
        """
        return self.filter(
            subject_content_type = ContentType.objects.get_for_model(subject),
            subject_object_id = subject.pk,
        ).exclude(public=False).order_by('-timestamp')
        
class Action(models.Model):
    """
    Action model describing the actor acting out a verb (on an optional target). 
    Nomenclature based on http://martin.atkins.me.uk/specs/activitystreams/atomactivity
    
    Generalized Format::
    
        <actor> <verb> <time>
        <actor> <verb> <target> <time>
    
    Examples::
    
        <justquick> <reached level 60> <1 minute ago>
        <brosner> <commented on> <pinax/pinax> <2 hours ago>
        <washingtontimes> <started follow> <justquick> <8 minutes ago>
        
    Unicode Representation::
    
        justquick reached level 60 1 minute ago
        
    HTML Representation::
    
        <a href="http://oebfare.com/">brosner</a> commented on <a href="http://github.com/pinax/pinax">pinax/pinax</a> 2 hours ago

    """
    actor_content_type = models.ForeignKey(ContentType,related_name='actor')
    actor_object_id = models.PositiveIntegerField() 
    actor = generic.GenericForeignKey('actor_content_type','actor_object_id')
    
    verb = models.CharField(max_length=255)
    description = models.TextField(blank=True,null=True)
    
    subject_content_type = models.ForeignKey(ContentType,related_name='subject',blank=True,null=True)
    subject_object_id = models.PositiveIntegerField(blank=True,null=True) 
    subject = generic.GenericForeignKey('subject_content_type','subject_object_id')
    
    target_content_type = models.ForeignKey(ContentType,related_name='target',blank=True,null=True)
    target_object_id = models.PositiveIntegerField(blank=True,null=True) 
    target = generic.GenericForeignKey('target_content_type','target_object_id')

    public = models.BooleanField(default=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    objects = ActionManager()
    
    def __unicode__(self):
        if self.target:
            return u'%s %s %s %s ago' % \
                (self.actor, self.verb, self.target, self.timesince())
        return u'%s %s %s ago' % (self.actor, self.verb, self.timesince())
        
    def actor_url(self):
        """
        Returns the URL to the ``actstream_actor`` view for the current actor
        """
        return reverse('actstream_actor', None,
                       (self.actor_content_type.pk, self.actor_object_id))
        
    def target_url(self):
        """
        Returns the URL to the ``actstream_actor`` view for the current target
        """        
        return reverse('actstream_actor', None,
                       (self.target_content_type.pk, self.target_object_id))
                
        
    def timesince(self, now=None):
        """
        Shortcut for the ``django.utils.timesince.timesince`` function of the current timestamp
        """
        return timesince_(self.timestamp, now)

    @models.permalink
    def get_absolute_url(self):
        return ('actstream.views.detail', [self.pk])
        

def follow(user, subject):
    """
    Creates a ``User`` -> ``Actor`` follow relationship such that the subject's activities appear in the user's stream.
    Also sends the ``<user> started following <subject>`` action signal.
    Returns the created ``Follow`` instance
    
    Syntax::
    
        follow(<user>, <subject>)
    
    Example::
    
        follow(request.user, group)
    
    """
    if not (settings.get('ACTIVITY_HIDE_FOLLOWING')):
        action.send(user, verb=_('started following'), target=subject)
    return Follow.objects.create(user = user, object_id = subject.pk, 
        content_type = ContentType.objects.get_for_model(subject))
    
def unfollow(user, subject, send_action=False):
    """
    Removes ``User`` -> ``Actor`` follow relationship. 
    Optionally sends the ``<user> stopped following <subject>`` action signal.
    
    Syntax::
    
        unfollow(<user>, <subject>)
    
    Example::
    
        unfollow(request.user, other_user)
    
    """
    Follow.objects.filter(user = user, object_id = subject.pk, 
        content_type = ContentType.objects.get_for_model(subject)).delete()
    if send_action:
        action.send(user, verb=_('stopped following'), target=subject)
    
def actor_stream(actor):
    return Action.objects.stream_for_actor(actor)
actor_stream.__doc__ = Action.objects.stream_for_actor.__doc__
    
def subject_stream(subject):
    return Action.objects.stream_for_subject(subject)
subject_stream.__doc__ = Action.objects.stream_for_subject.__doc__
    
def user_stream(user):
    return Follow.objects.stream_for_user(user)
user_stream.__doc__ = Follow.objects.stream_for_user.__doc__
    
def model_stream(model):
    return Action.objects.stream_for_model(model)
model_stream.__doc__ = Action.objects.stream_for_model.__doc__

    
def action_handler(verb, target=None, public=True, subject='actor', **kwargs):
    actor = kwargs.pop('sender')
    kwargs.pop('signal', None)
    kw = {
        'actor_content_type': ContentType.objects.get_for_model(actor),
        'actor_object_id': actor.pk,
        'verb': unicode(verb),
        'public': bool(public),
    }
    if subject=='actor':
        kw.update(subject_object_id=actor.pk,
            subject_content_type=ContentType.objects.get_for_model(actor))
    elif subject=='target':
        kw.update(subject_object_id=target.pk,
            subject_content_type=ContentType.objects.get_for_model(target))
    else:
        #assume the subject is some other model
        try:
            subject_object_id = subject.pk
        except AttributeError, inst:
            raise Exception("Invalid model/object: did not have a primary key: %s" % (type(subject), subject,inst))
        try:
            subject_content_type = ContentType.objects.get_for_model(subject)
        except Exception, inst:
            raise Exception("Invalid model/object: was not a recognized content type: %s (%s)" % (inst,type(inst)))
        kw.update(subject_object_id=subject_object_id,
            subject_content_type=subject_content_type)
            
    if target:
        kw.update(target_object_id=target.pk,
            target_content_type=ContentType.objects.get_for_model(target))
    kw.update(kwargs)
    Action.objects.get_or_create(**kw)[0]
    
action.connect(action_handler)
