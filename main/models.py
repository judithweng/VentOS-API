import uuid

from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

# Create your models here.


class PIRCS(models.Model):
    com = models.CharField(max_length=1)
    par = models.CharField(max_length=1)
    int = models.CharField(max_length=1)
    mod = models.IntegerField()
    val = models.IntegerField()

    def __str__(self) -> str:
        return ("com: " + self.com + ", par: " + self.par + ", loc: "
                + self.int + ", mod: " + str(self.mod) + ", val: " + str(self.val))


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


class PatientState(models.Model):
    time = models.FloatField()
    TLC = models.FloatField()
    pressure_mouth = models.FloatField()
    resistance = models.FloatField()
    pressure_alveolus = models.FloatField()
    lung_volume = models.FloatField()
    pressure_intrapleural = models.FloatField()
    flow = models.FloatField()
    log = models.JSONField()

    def __str__(self) -> str:
        return str(self.log[-1])


class VentilatorState(models.Model):
    pressure = models.FloatField()
    pressure_mouth = models.FloatField()
    mode = models.CharField(max_length=3)
    Pi = models.FloatField()
    PEEP = models.FloatField()
    rate = models.FloatField()
    IE = models.FloatField()
    phase = models.CharField(max_length=1)
    log = models.JSONField()
    time = models.FloatField()

    def __str__(self) -> str:
        return str(self.log[-1])
