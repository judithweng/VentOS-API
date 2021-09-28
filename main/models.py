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
