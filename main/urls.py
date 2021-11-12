from django.urls import path
from . import views

urlpatterns = [
    # path('control/', views.control, name='control'),
    # path('data/', views.data, name='data'),

    # look for some string in our path, and pass that to views.control
    # dynamic pages in terms of linking
    path('<int:n>', views.data, name='data'),

    # for inputting PIRCS commands (+UI)
    path('control/', views.control, name='control'),

    # for any "badness" scenario
    path('badness/', views.badness, name='badness'),
]
