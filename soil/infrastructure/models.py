from peewee import Model, AutoField, IntegerField, FloatField, DateTimeField, BooleanField, CharField

from shared.infrastructure.database import db


class SoilReading(Model):
    id                   = AutoField()
    device_id            = IntegerField()
    farm_id              = IntegerField()
    zone_id              = IntegerField(null=True)
    moisture             = FloatField()
    ec                   = FloatField()
    ph                   = FloatField()
    temperature          = FloatField()
    recorded_at          = DateTimeField()
    is_valid             = BooleanField(default=True)
    synced               = BooleanField(default=False)
    ambient_temperature  = FloatField(null=True)
    security_pir_status  = CharField(null=True, max_length=32)

    class Meta:
        database   = db
        table_name = "soil_readings"