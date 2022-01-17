import uuid

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

# Create your models here.


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    height = models.FloatField()
    weight = models.FloatField()
    sex = models.CharField(max_length=1)
    resistance = models.FloatField()
    compliance = models.FloatField()

    def __str__(self) -> str:
        return ("id: " + str(self.id) + ", name: " + self.name + ", height: " + str(self.height) +
                " cm, weight: " + str(self.weight) + " kg, sex: " + self.sex +
                ", resistance: " + str(self.resistance) + ", compliance: " + str(self.compliance))


class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return ("session id: " + str(self.id))


class PIRCS(models.Model):
    com = models.CharField(max_length=1)
    par = models.CharField(max_length=1)
    int = models.CharField(max_length=1)
    mod = models.IntegerField()
    val = models.IntegerField()
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, default=None)

    def __str__(self) -> str:
        return ("sid: " + str(self.session) + ", com: " + self.com + ", par: " + self.par + ", loc: "
                + self.int + ", mod: " + str(self.mod) + ", val: " + str(self.val))


class PatientState(models.Model):
    timestamp = models.FloatField()
    TLC = models.FloatField()
    pressure_mouth = models.FloatField()
    resistance = models.FloatField()
    pressure_alveolus = models.FloatField()
    lung_volume = models.FloatField()
    pressure_intrapleural = models.FloatField()
    flow = models.FloatField()
    log = models.JSONField()
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, default=None)

    def __str__(self) -> str:
        if len(self.log) == 0:
            return ("sid: " + str(self.session) + ", time: " + str(self.timestamp) + " - log is not yet available")
        else:
            return ("sid: " + str(self.session) + ", time: " + str(self.timestamp) + " - last logged patient state: " + str(self.log[-1]))


class VentilatorState(models.Model):
    timestamp = models.FloatField()
    pressure = models.FloatField()
    pressure_mouth = models.FloatField()
    mode = models.CharField(max_length=3)
    Pi = models.FloatField()
    PEEP = models.FloatField()
    rate = models.FloatField()
    IE = models.FloatField()
    phase = models.CharField(max_length=1)
    log = models.JSONField()
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, default=None)

    def __str__(self) -> str:
        if len(self.log) == 0:
            return ("sid: " + str(self.session) + ", time: " + str(self.timestamp) + " - log is not yet available")
        else:
            return ("sid: " + str(self.session) + ", time: " + str(self.timestamp) + " - last logged ventilator state: " + str(self.log[-1]))
