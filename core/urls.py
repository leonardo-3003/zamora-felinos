from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("registros/", views.RegistroListView.as_view(), name="registro_list"),
    path("registros/nuevo/", views.RegistroCreateView.as_view(), name="registro_create"),
    path("registros/<int:pk>/editar/", views.RegistroUpdateView.as_view(), name="registro_update"),
    path("registros/exportar.csv", views.exportar_csv, name="exportar_csv"),
    path("registros/<int:registro_id>/consentimiento.pdf", views.generar_consentimiento_pdf, name="generar_consentimiento"),
    path("registros/<int:registro_id>/certificado.pdf", views.generar_certificado_pdf, name="generar_certificado"),
]
