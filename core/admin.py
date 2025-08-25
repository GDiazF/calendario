from django.contrib import admin
from .models import (
    Sexo, EstadoCivil, Region, Comuna, Empresa, Personal, DeptoEmpresa, 
    Cargo, InfoLaboral, TipoAusentismo, Ausentismo, TipoLicenciaMedica, 
    LicenciaMedicaPorPersonal, TipoTurno, Faena, PersonalFaena, AuditLog
)


@admin.register(Sexo)
class SexoAdmin(admin.ModelAdmin):
    list_display = ['sexo_id', 'sexo']
    search_fields = ['sexo']


@admin.register(EstadoCivil)
class EstadoCivilAdmin(admin.ModelAdmin):
    list_display = ['estcivil_id', 'estado']
    search_fields = ['estado']


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ['region_id', 'nombre']
    search_fields = ['nombre']


@admin.register(Comuna)
class ComunaAdmin(admin.ModelAdmin):
    list_display = ['comuna_id', 'nombre', 'region_id']
    list_filter = ['region_id']
    search_fields = ['nombre']


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ['empresa_id', 'nombre']
    search_fields = ['nombre']


@admin.register(Personal)
class PersonalAdmin(admin.ModelAdmin):
    list_display = ['personal_id', 'nombre', 'apepat', 'apemat', 'rut', 'dvrut', 'activo']
    list_filter = ['activo', 'sexo_id', 'estcivil_id', 'region_id']
    search_fields = ['nombre', 'apepat', 'apemat', 'rut']
    readonly_fields = ['personal_id']


@admin.register(DeptoEmpresa)
class DeptoEmpresaAdmin(admin.ModelAdmin):
    list_display = ['depto_id', 'depto']
    search_fields = ['depto']


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ['cargo_id', 'cargo', 'depto_id']
    list_filter = ['depto_id']
    search_fields = ['cargo']


@admin.register(InfoLaboral)
class InfoLaboralAdmin(admin.ModelAdmin):
    list_display = ['infolab_id', 'personal_id', 'empresa_id', 'faena_id', 'depto_id', 'cargo_id', 'fechacontrata']
    list_filter = ['empresa_id', 'faena_id', 'depto_id', 'cargo_id', 'fechacontrata']
    search_fields = ['personal_id__nombre', 'personal_id__apepat', 'personal_id__apemat']
    readonly_fields = ['infolab_id']


@admin.register(TipoAusentismo)
class TipoAusentismoAdmin(admin.ModelAdmin):
    list_display = ['tipoausen_id', 'tipo']
    search_fields = ['tipo']


@admin.register(Ausentismo)
class AusentismoAdmin(admin.ModelAdmin):
    list_display = ['ausentismo_id', 'personal_id', 'tipoausen_id', 'fechaini', 'fechafin']
    list_filter = ['tipoausen_id', 'fechaini', 'fechafin']
    search_fields = ['personal_id__nombre', 'personal_id__apepat', 'personal_id__apemat']
    readonly_fields = ['ausentismo_id']


@admin.register(TipoLicenciaMedica)
class TipoLicenciaMedicaAdmin(admin.ModelAdmin):
    list_display = ['tipoLicenciaMedica_id', 'tipoLicenciaMedica']
    search_fields = ['tipoLicenciaMedica']


@admin.register(LicenciaMedicaPorPersonal)
class LicenciaMedicaPorPersonalAdmin(admin.ModelAdmin):
    list_display = ['licenciaMedicaPorPersonal_id', 'personal_id', 'tipoLicenciaMedica_id', 'fechaEmision', 'dias_licencia', 'fecha_fin_licencia']
    list_filter = ['tipoLicenciaMedica_id', 'fechaEmision', 'fecha_fin_licencia']
    search_fields = ['personal_id__nombre', 'personal_id__apepat', 'personal_id__apemat', 'numero_folio']
    readonly_fields = ['licenciaMedicaPorPersonal_id', 'fecha_fin_licencia']


@admin.register(TipoTurno)
class TipoTurnoAdmin(admin.ModelAdmin):
    list_display = ['tipo_turno_id', 'nombre', 'dias_trabajo', 'dias_descanso', 'duracion_ciclo', 'activo']
    list_filter = ['activo']
    search_fields = ['nombre']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'dias_trabajo', 'dias_descanso', 'activo')
        }),
        ('Información del Sistema', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Faena)
class FaenaAdmin(admin.ModelAdmin):
    list_display = ['faena_id', 'nombre', 'tipo_turno', 'fecha_inicio', 'fecha_fin', 'activo']
    list_filter = ['activo', 'tipo_turno', 'fecha_inicio', 'fecha_fin']
    search_fields = ['nombre', 'ubicacion', 'descripcion']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']
    date_hierarchy = 'fecha_inicio'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('nombre', 'tipo_turno', 'ubicacion', 'descripcion', 'activo')
        }),
        ('Fechas de la Faena', {
            'fields': ('fecha_inicio', 'fecha_fin'),
            'description': 'Define el período de duración de la faena'
        }),
        ('Información del Sistema', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar consultas"""
        return super().get_queryset(request).select_related('tipo_turno')


@admin.register(PersonalFaena)
class PersonalFaenaAdmin(admin.ModelAdmin):
    list_display = ['personal_faena_id', 'personal', 'faena', 'tipo_turno', 'fecha_inicio', 'fecha_fin_calculada', 'activo', 'esta_activa']
    list_filter = ['activo', 'faena', 'tipo_turno', 'fecha_inicio']
    search_fields = ['personal__nombre', 'personal__apepat', 'personal__apemat', 'faena__nombre']
    readonly_fields = ['personal_faena_id', 'fecha_asignacion', 'fecha_creacion', 'fecha_modificacion', 'fecha_fin_calculada', 'duracion_dias', 'proximo_cambio_turno']
    date_hierarchy = 'fecha_inicio'
    
    fieldsets = (
        ('Asignación', {
            'fields': ('personal', 'faena', 'activo')
        }),
        ('Período de Asignación', {
            'fields': ('fecha_inicio', 'tipo_turno'),
            'description': 'Define cuándo entra la persona y qué turno tendrá (usa el de la faena si no se especifica)'
        }),
        ('Información Calculada', {
            'fields': ('fecha_fin_calculada', 'duracion_dias', 'proximo_cambio_turno'),
            'description': 'Estos campos se calculan automáticamente basándose en el turno y la duración de la faena',
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
        ('Información del Sistema', {
            'fields': ('fecha_asignacion', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimizar consultas"""
        return super().get_queryset(request).select_related('personal', 'faena', 'tipo_turno')


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['log_id', 'usuario', 'accion', 'tabla_afectada', 'registro_id', 'fecha_hora', 'ip_address']
    list_filter = ['accion', 'tabla_afectada', 'fecha_hora', 'usuario']
    search_fields = ['usuario', 'accion', 'tabla_afectada', 'descripcion']
    readonly_fields = ['log_id', 'fecha_hora']
    date_hierarchy = 'fecha_hora'
    
    fieldsets = (
        ('Información del Cambio', {
            'fields': ('usuario', 'accion', 'tabla_afectada', 'registro_id', 'descripcion')
        }),
        ('Datos del Cambio', {
            'fields': ('datos_anteriores', 'datos_nuevos', 'detalles_adicionales'),
            'classes': ('collapse',)
        }),
        ('Información del Sistema', {
            'fields': ('fecha_hora', 'ip_address'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """No permitir crear logs manualmente"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """No permitir editar logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """No permitir eliminar logs"""
        return False
