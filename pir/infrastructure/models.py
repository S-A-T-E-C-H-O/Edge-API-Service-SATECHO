from peewee import Model, AutoField, IntegerField, FloatField, CharField, DateTimeField

from shared.infrastructure.database import db


class PirEvent(Model):
    id                  = AutoField()
    device_id           = IntegerField()
    farm_id             = IntegerField()
    zone_id             = IntegerField(null=True)
    pulse_duration_ms   = FloatField()
    triggers_per_minute = IntegerField()
    classification      = CharField()   # WIND | ANIMAL | PERSON
    recorded_at         = DateTimeField()

    class Meta:
        database   = db
        table_name = "pir_events"