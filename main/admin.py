from django.contrib import admin
from .models import PIRCS, PatientState, VentilatorState, Session, Person
# Register your models here.
admin.site.register(PIRCS)
admin.site.register(Person)
admin.site.register(PatientState)
admin.site.register(VentilatorState)
admin.site.register(Session)
