from django.db.models.query import QuerySet
from django.db.models import Manager
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.generic import GenericForeignKey
from django.conf import settings
from django.db import models

class GFKManager(Manager):
    """
    A manager that returns a GFKQuerySet instead of a regular QuerySet.

    """
    def get_query_set(self):
        return GFKQuerySet(self.model)

class GFKQuerySet(QuerySet):
    """
    A QuerySet with a fetch_generic_relations() method to bulk fetch
    all generic related items.  Similar to select_related(), but for
    generic foreign keys.

    Based on http://www.djangosnippets.org/snippets/984/
    Firstly improved at http://www.djangosnippets.org/snippets/1079/

    """
    def __init__(self, *args, **kwargs):
        try:
            app_label, model_name = settings.AUTH_PROFILE_MODULE.split('.')
            self.profile_module = models.get_model(app_label, model_name)._meta.module_name
        except AttributeError, inst:
            self.profile_module = None
        super(GFKQuerySet,self).__init__(*args, **kwargs)
    
    def fetch_generic_relations(self):
        qs = self._clone()

        gfk_fields = [g for g in self.model._meta.virtual_fields if isinstance(g, GenericForeignKey)]
        
        ct_map = {}
        item_map = {}
        data_map = {}
        model_map = {}        
        
        for item in qs:
            for gfk in gfk_fields:
                ct_id_field = selfmodel._meta.get_field(gfk.ct_field).column
                #print "ct_id=%s" % getattr(item, ct_id_field)
                #print "item_id=%s" % getattr(item, gfk.fk_field)
                #print "%s %s" % (ct_id_field, getattr(item, ct_id_field))
                ct_map.setdefault(
                    (getattr(item, ct_id_field)), {}
                    )[getattr(item, gfk.fk_field)] = (gfk.name, item.id)
            item_map[item.id] = item

        for (ct_id), items_ in ct_map.items():
            if (ct_id):
                ct = ContentType.objects.get_for_id(ct_id)
                related_fields = ["user__pk"]
                if self.profile_module:
                    related_fields.append("user_%s__pk" % self.profile_module)
                for o in ct.model_class().objects.select_related(*related_fields).filter(id__in=items_.keys()).all():
                    (gfk_name, item_id) = items_[o.id]
                    data_map[(ct_id, o.id)] = o

        missing_records = {}
        for item in qs:
            for gfk in gfk_fields:
                print "getattr(item, '%s', None)=%s" % (gfk.name, getattr(item, gfk.name, None)) 
                if (getattr(item, gfk.fk_field) != None):
                    ct_id_field = self.model._meta.get_field(gfk.ct_field).column
                    try:
                        setattr(item, gfk.name, data_map[(getattr(item, ct_id_field), getattr(item, gfk.fk_field))])
                    except KeyError:
                        if ((self.model._meta.get_field(gfk.ct_field).null or self.model._meta.get_field(gfk.ct_field).blank) and 
                            (self.model._meta.get_field(gfk.fk_field).null or self.model._meta.get_field(gfk.fk_field).blank)
                        ):
                            setattr(item, gfk.name, None)
                        else:
                            missing_records.setdefault(
                            )
                            missing_records.append({ "%s__pk" % gfk.ct_field : getattr(item, ct_id_field), self.model._meta.get_field(gfk.fk_field).column : getattr(item, gfk.fk_field) })

        for mr in missing_records:
            print 
            qs = qs.exclude(**mr)
        return qs
