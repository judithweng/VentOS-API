from django.urls import path
from . import views

urlpatterns = [
    # look for some string in our path, and pass that to views.control
    # dynamic pages in terms of linking
    path('<int:n>', views.data, name='data'),

    # for inputting PIRCS commands (+UI)
    path('control/', views.control, name='control'),

    path('', views.home, name='home'),

    path('patient/', views.patient_info, name='patient')
]
