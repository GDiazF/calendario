from django.urls import path
from . import views

urlpatterns = [
    path('', views.calendar_view, name='planning_calendar'),
    path('get_personas/', views.get_personas, name='get_personas'),
    path('get_faenas/', views.get_faenas, name='get_faenas'),
    path('get_faenas_for_audit/', views.get_faenas_for_audit, name='get_faenas_for_audit'),
    path('get_cargos/', views.get_cargos, name='get_cargos'),
    path('get_estados/', views.get_estados, name='get_estados'),
    path('get_turnos/', views.get_turnos, name='get_turnos'),
    path('get_faena_turno/<int:faena_id>/', views.get_faena_turno, name='get_faena_turno'),
    path('assign_personal_to_faena/', views.assign_personal_to_faena, name='assign_personal_to_faena'),
    path('remove_personal_from_faena/', views.remove_personal_from_faena, name='remove_personal_from_faena'),
    path('get_audit_logs/', views.get_audit_logs, name='get_audit_logs'),
]


