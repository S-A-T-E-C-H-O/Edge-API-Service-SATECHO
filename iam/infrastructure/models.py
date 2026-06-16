from peewee import Model, IntegerField, CharField, DateTimeField

from shared.infrastructure.database import db


class Device(Model):
    device_id  = IntegerField(primary_key=True)
    farm_id    = IntegerField()
    api_key    = CharField()
    created_at = DateTimeField()

    class Meta:
        database   = db
        table_name = "devices"from peewee import Model, IntegerField, CharField, DateTimeField

from shared.infrastructure.database import db


class Device(Model):
    device_id  = IntegerField(primary_key=True)
    farm_id    = IntegerField()
    api_key    = CharField()
    created_at = DateTimeField()

    class Meta:
        database   = db
        table_name = "devices"