# =============================================================================
# IMPORTS Y CONFIGURACIÓN
# =============================================================================

# Importaciones estándar de Python para manejo de fechas y calendarios
from datetime import date
from calendar import monthrange
from datetime import timedelta

# Importaciones de Django para manejo de HTTP, vistas y base de datos
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.db.models import Q
from django.utils import timezone

# Importación para manejo de idioma español en fechas
import locale

# =============================================================================
# CONFIGURACIÓN DE IDIOMA ESPAÑOL PARA FECHAS
# =============================================================================

# Intentar configurar el locale para fechas en español
# Se prueban diferentes formatos según el sistema operativo
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain.1252')
    except:
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES')
        except:
            # Si no se puede configurar el locale, usar inglés por defecto
            pass

# =============================================================================
# IMPORTACIONES DE MODELOS DE LA BASE DE DATOS
# =============================================================================

# Importar todos los modelos necesarios para el calendario
from core.models import (
    Personal,           # Modelo principal de personal/empleados
    Cargo,             # Modelo de cargos/puestos de trabajo
    DeptoEmpresa,      # Modelo de departamentos de la empresa
    Empresa,           # Modelo de empresas
    Faena,             # Modelo de faenas/proyectos
    TipoTurno,         # Modelo de tipos de turnos (7x7, 14x7, etc.)
    Ausentismo,        # Modelo de ausentismos (vacaciones, permisos, etc.)
    LicenciaMedicaPorPersonal,  # Modelo de licencias médicas
    PersonalFaena,     # Modelo de asignación de personal a faenas
    AuditLog,          # Modelo de logs de auditoría
)


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def get_client_ip(request):
    """
    Obtener la IP del cliente desde el request
    Útil para logs de auditoría y seguridad
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_current_user_name(request):
    """
    Obtener el nombre del usuario actual autenticado
    Se usa para identificar quién realiza cambios en el sistema
    """
    if request.user.is_authenticated:
        if request.user.first_name and request.user.last_name:
            return f"{request.user.first_name} {request.user.last_name}"
        elif request.user.username:
            return request.user.username
        else:
            return request.user.email
    return 'Usuario no autenticado'


# =============================================================================
# VISTA PRINCIPAL DEL CALENDARIO
# =============================================================================

def calendar_view(request):
    """
    Vista principal del calendario de planificación
    Renderiza la página HTML del calendario con el mes y año especificados
    """
    today = date.today()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    days_in_month = monthrange(year, month)[1]
    
    context = {
        'year': year,
        'month': month,
        'days_in_month': days_in_month,
    }
    return render(request, 'planning/calendar.html', context)


# =============================================================================
# API PARA OBTENER PERSONAL FILTRADO
# =============================================================================

@require_GET
def get_personas(request):
    """
    Obtener lista de personas filtradas por faena y cargos
    
    Esta función es el corazón del sistema de filtrado del calendario:
    - Filtra personal por cargos específicos (RIGGER, OPERADOR, etc.)
    - Filtra por faenas asignadas o sin asignar
    - Obtiene información detallada de cada persona
    - Incluye faenas actuales, cargos y datos personales
    
    Parámetros de entrada:
    - cargos[]: Lista de IDs de cargos para filtrar
    - faena_id: ID de faena específica o 'sin_asignar'
    
    Retorna: JSON con lista de personas y sus datos completos
    """
    
    # =============================================================================
    # OBTENER PARÁMETROS DE FILTRADO
    # =============================================================================
    
    # Intentar diferentes formas de obtener los cargos (compatibilidad con frontend)
    cargos_filter = request.GET.getlist('cargos')
    if not cargos_filter:
        cargos_filter = request.GET.getlist('cargos[]')
    if not cargos_filter:
        cargos_filter = request.GET.getlist('cargo_id')
    
    # Obtener ID de faena para filtrar (puede ser específica o 'sin_asignar')
    faena_id = request.GET.get('faena_id')
    
    # =============================================================================
    # DEBUG: IMPRIMIR PARÁMETROS RECIBIDOS
    # =============================================================================
    
    # Debug: imprimir los parámetros recibidos
    print(f"DEBUG: cargos_filter recibido: {cargos_filter}")
    print(f"DEBUG: faena_id recibido: {faena_id}")
    print(f"DEBUG: request.GET completo: {dict(request.GET)}")
    print(f"DEBUG: request.GET.getlist('cargos'): {request.GET.getlist('cargos')}")
    print(f"DEBUG: request.GET.getlist('cargos[]'): {request.GET.getlist('cargos[]')}")
    print(f"DEBUG: request.GET.getlist('cargo_id'): {request.GET.getlist('cargo_id')}")
    
    # =============================================================================
    # VERIFICAR ASIGNACIONES A LA FAENA SELECCIONADA (DEBUG)
    # =============================================================================
    
    # Si se selecciona una faena específica, verificar todas las asignaciones
    if faena_id and faena_id != 'sin_asignar':
        print(f"DEBUG: Verificando todas las asignaciones a la faena {faena_id}")
        todas_asignaciones = PersonalFaena.objects.filter(
            faena_id=faena_id,
            activo=True
        ).select_related('personal', 'faena')
        print(f"DEBUG: Total de asignaciones activas a la faena {faena_id}: {todas_asignaciones.count()}")
        for asignacion in todas_asignaciones:
            print(f"DEBUG: Asignación encontrada - Personal ID: {asignacion.personal_id}, Nombre: {asignacion.personal.nombre} {asignacion.personal.apepat}, Faena: {asignacion.faena.nombre}, Activo: {asignacion.activo}")
    elif faena_id == 'sin_asignar':
        print(f"DEBUG: Modo 'SIN ASIGNAR' - no se verificarán asignaciones específicas")

    # =============================================================================
    # QUERY BASE: OBTENER TODO EL PERSONAL ACTIVO
    # =============================================================================
    
    # Obtener todas las personas activas en el sistema
    personas_qs = Personal.objects.filter(activo=True)
    print(f"DEBUG: Total de personal activo: {personas_qs.count()}")
    
    # =============================================================================
    # VERIFICAR RELACIÓN INFOLABORAL (DEBUG)
    # =============================================================================
    
    # Debug: verificar que la relación InfoLaboral funcione correctamente
    try:
        test_person = personas_qs.first()
        if test_person:
            infolaboral_count = test_person.infolaboral_set.count()
            print(f"DEBUG: Persona de prueba {test_person.personal_id} tiene {infolaboral_count} registros en InfoLaboral")
            if infolaboral_count > 0:
                cargo_test = test_person.infolaboral_set.first().cargo_id
                print(f"DEBUG: Cargo de prueba: {cargo_test.cargo_id} - {cargo_test.cargo}")
    except Exception as e:
        print(f"DEBUG: Error al verificar InfoLaboral: {e}")
    
    # =============================================================================
    # FILTRADO POR CARGOS (PRIMER FILTRO)
    # =============================================================================
    
    # Aplicar filtro de cargos si se especifican
    if cargos_filter:
        print(f"DEBUG: Aplicando filtro de cargos: {cargos_filter}")
        
        # Filtrar por múltiples cargos usando Q objects para OR lógico
        from django.db.models import Q
        cargo_filters = Q()
        for cargo_id in cargos_filter:
            cargo_filters |= Q(infolaboral__cargo_id=cargo_id)
        
        # Aplicar el filtro de cargos
        personas_qs = personas_qs.filter(cargo_filters)
        print(f"DEBUG: Query de cargos aplicado: {cargo_filters}")
        print(f"DEBUG: Personas después del filtro de cargos: {personas_qs.count()}")
        
        # Debug adicional: ver qué cargos tienen las personas
        for persona in personas_qs:
            cargos_persona = persona.infolaboral_set.values_list('cargo_id__cargo', flat=True)
            print(f"DEBUG: Persona {persona.personal_id} tiene cargos: {list(cargos_persona)}")
        
        print(f"DEBUG: Personas después del filtro de cargos (antes del filtro de faena): {personas_qs.count()}")
        for persona in personas_qs:
            print(f"DEBUG: Persona {persona.personal_id} - {persona.nombre} {persona.apepat} - Cargos: {list(persona.infolaboral_set.values_list('cargo_id__cargo', flat=True))}")
    else:
        print("DEBUG: No hay filtro de cargos aplicado")
        # Si no hay cargos seleccionados, no mostrar personal
        personas_qs = Personal.objects.none()
        print("DEBUG: No se mostrará personal porque no hay cargos seleccionados")
    
    # =============================================================================
    # FILTRADO POR FAENA (SEGUNDO FILTRO)
    # =============================================================================
    
    # Aplicar filtro de faena si se especifica
    if faena_id:
        if faena_id == 'sin_asignar':
            print(f"DEBUG: Aplicando filtro 'SIN ASIGNAR'")
            # Filtrar personas que NO tienen faenas asignadas activas
            personas_qs = personas_qs.exclude(
                personalfaena__activo=True
            )
            print(f"DEBUG: Personas sin asignar: {personas_qs.count()}")
        else:
            print(f"DEBUG: Aplicando filtro de faena {faena_id}")
            # Filtrar personas que SÍ tienen la faena específica asignada
            personas_qs = personas_qs.filter(
                personalfaena__faena_id=faena_id,
                personalfaena__activo=True
            )
            print(f"DEBUG: Personas después del filtro de faena: {personas_qs.count()}")
        
        # Debug: mostrar qué personas pasan el filtro de faena
        for persona in personas_qs:
            print(f"DEBUG: Persona {persona.personal_id} - {persona.nombre} {persona.apepat} - Pasa filtro de faena")

    # =============================================================================
    # OPTIMIZACIÓN DE QUERY
    # =============================================================================
    
    # Eliminar duplicados y optimizar con select_related
    personas_qs = personas_qs.distinct().select_related()

    # =============================================================================
    # OBTENER INFORMACIÓN DETALLADA DE FAENAS Y CARGOS
    # =============================================================================
    
    # Diccionarios para almacenar información de faenas y cargos por persona
    faenas_actuales = {}
    cargos_actuales = {}
    from datetime import date
    today = date.today()
    
    # =============================================================================
    # CONSULTA DE ASIGNACIONES DE FAENA
    # =============================================================================
    
    # Si se filtra por faena específica, obtener solo las asignaciones a esa faena
    if faena_id and faena_id != 'sin_asignar':
        asignaciones = PersonalFaena.objects.filter(
            personal_id__in=personas_qs,
            faena_id=faena_id,
            activo=True
        ).values('personal_id', 'faena__nombre', 'faena_id', 'fecha_inicio', 'tipo_turno__nombre', 'faena__tipo_turno__nombre')
    else:
        # Si no se filtra por faena o es 'sin_asignar', obtener todas las faenas activas de las personas
        asignaciones = PersonalFaena.objects.filter(
            personal_id__in=personas_qs,
            activo=True
        ).values('personal_id', 'faena__nombre', 'faena_id', 'fecha_inicio', 'tipo_turno__nombre', 'faena__tipo_turno__nombre')
    
    # Debug: imprimir las asignaciones encontradas
    print(f"DEBUG: Asignaciones encontradas: {list(asignaciones)}")
    
    # =============================================================================
    # PROCESAR ASIGNACIONES Y CONSTRUIR INFORMACIÓN DE FAENAS
    # =============================================================================
    
    # Agrupar múltiples faenas por persona
    for asignacion in asignaciones:
        personal_id = asignacion['personal_id']
        if personal_id not in faenas_actuales:
            faenas_actuales[personal_id] = []
        
        # Construir información de la faena con lógica de turno mejorada
        # Si no hay turno específico asignado, usar el turno de la faena
        turno_info = asignacion['tipo_turno__nombre'] or asignacion['faena__tipo_turno__nombre'] or 'Turno no especificado'
        
        faenas_actuales[personal_id].append({
            'nombre': asignacion['faena__nombre'],
            'faena_id': asignacion['faena_id'],
            'fecha_inicio': asignacion['fecha_inicio'].isoformat() if asignacion['fecha_inicio'] else None,
            'turno': turno_info
        })
        print(f"DEBUG: Asignación para personal {personal_id}: {asignacion['faena__nombre']}")
    
    # =============================================================================
    # OBTENER CARGOS ACTUALES DE CADA PERSONA
    # =============================================================================
    
    # Para cada persona, obtener su cargo más reciente desde InfoLaboral
    for persona in personas_qs:
        cargos = persona.infolaboral_set.values_list('cargo_id__cargo', flat=True)
        if cargos:
            cargos_actuales[persona.personal_id] = ', '.join(cargos)
        else:
            cargos_actuales[persona.personal_id] = 'Sin cargo'
        print(f"DEBUG: Cargo para personal {persona.personal_id}: {cargos_actuales[persona.personal_id]}")

    # =============================================================================
    # CONSTRUIR RESPUESTA FINAL PARA EL FRONTEND
    # =============================================================================
    
    # Lista que contendrá todos los datos de las personas
    data = []
    for p in personas_qs:
        # Obtener faenas y cargo de la persona
        faenas_persona = faenas_actuales.get(p.personal_id, [])
        cargo_actual = cargos_actuales.get(p.personal_id, 'Sin cargo')
        
        # Para compatibilidad, mantener faena_actual como string (primera faena)
        faena_actual = faenas_persona[0]['nombre'] if faenas_persona else None
        
        # Construir objeto de datos de la persona
        data.append({
            'id': p.personal_id,
            'nombre': f"{p.nombre} {p.apepat} {p.apemat}",
            'rut': f"{p.rut}-{p.dvrut}",
            'faena_actual': faena_actual,
            'faenas_detalladas': faenas_persona,  # Nueva información detallada
            'cargo_actual': cargo_actual,
            'correo': p.correo,
            'direccion': p.direccion,
            'comuna_nombre': p.comuna_id.nombre if p.comuna_id else None,
            'fechanac': p.fechanac
        })
        
        # Debug: imprimir los datos de cada persona
        print(f"DEBUG: Persona {p.personal_id}: faena_actual = {faena_actual}, faenas_detalladas = {faenas_persona}, cargo_actual = {cargo_actual}")
    
    # Debug: imprimir el resultado final
    print(f"DEBUG: Datos enviados al frontend: {data}")
    
    # Retornar respuesta JSON con todas las personas filtradas
    return JsonResponse({'results': data})


# =============================================================================
# API PARA OBTENER FAENAS
# =============================================================================

@require_GET
def get_faenas(request):
    """
    Obtener lista de todas las faenas activas más opción 'Sin Asignar'
    
    Esta función proporciona la lista de faenas para los filtros del frontend:
    - Obtiene todas las faenas activas del sistema
    - Incluye fechas de inicio y fin de cada faena
    - Agrega opción "SIN ASIGNAR" para mostrar personal sin faena
    
    Retorna: JSON con lista de faenas y opción "SIN ASIGNAR"
    """
    
    # Obtener todas las faenas activas ordenadas por nombre
    faenas = Faena.objects.filter(
        activo=True
    ).values('faena_id', 'nombre', 'fecha_inicio', 'fecha_fin').order_by('nombre')
    
    # Construir lista de datos de faenas
    data = [
        {
            'id': item['faena_id'], 
            'nombre': item['nombre'],
            'fecha_inicio': item['fecha_inicio'].strftime('%Y-%m-%d') if item['fecha_inicio'] else None,
            'fecha_fin': item['fecha_fin'].strftime('%Y-%m-%d') if item['fecha_fin'] else None
        } 
        for item in faenas
    ]
    
    # Agregar opción "SIN ASIGNAR" al final para filtrar personal sin faena
    data.append({
        'id': 'sin_asignar',
        'nombre': 'SIN ASIGNAR',
        'fecha_inicio': None,
        'fecha_fin': None
    })
    
    return JsonResponse({'results': data})


def get_faenas_for_audit(request):
    """
    Obtener lista de solo faenas reales (sin 'Sin Asignar') para filtros de auditoría
    
    Esta función es específica para el panel de logs de auditoría:
    - Excluye la opción "SIN ASIGNAR" ya que no es una faena real
    - Solo incluye faenas activas del sistema
    - Se usa para filtrar logs por faena específica
    
    Retorna: JSON con lista de faenas reales únicamente
    """
    
    # Obtener solo faenas activas (sin opciones virtuales)
    faenas = Faena.objects.filter(
        activo=True
    ).values('faena_id', 'nombre').order_by('nombre')
    
    # Construir lista simple de faenas para filtros
    data = [
        {
            'id': item['faena_id'], 
            'nombre': item['nombre']
        } 
        for item in faenas
    ]
    
    return JsonResponse({'results': data})


# =============================================================================
# API PARA OBTENER CARGOS
# =============================================================================

@require_GET
def get_cargos(request):
    """
    Obtener todos los cargos disponibles en el sistema
    
    Esta función proporciona la lista de cargos para los filtros del frontend:
    - Obtiene todos los cargos del sistema (RIGGER, OPERADOR, etc.)
    - Se usa para filtrar personal por cargo específico
    - Ordena los cargos alfabéticamente
    
    Retorna: JSON con lista de todos los cargos disponibles
    """
    
    # Obtener todos los cargos ordenados alfabéticamente
    cargos = Cargo.objects.all().values('cargo_id', 'cargo').order_by('cargo')
    
    # Construir lista de cargos para el frontend
    data = [{'id': c['cargo_id'], 'nombre': c['cargo']} for c in cargos]
    return JsonResponse({'results': data})


# =============================================================================
# API PRINCIPAL: OBTENER ESTADOS DEL CALENDARIO
# =============================================================================

@require_GET
def get_estados(request):
    """
    OBTENER ESTADOS DE PERSONAS PARA UN MES ESPECÍFICO
    
    Esta es la función más importante del sistema de calendario:
    - Calcula el estado de cada persona para cada día del mes
    - Aplica múltiples capas de estados (faena, turno, descanso, licencias, etc.)
    - Respeta las fechas de inicio y fin de las faenas
    - Calcula automáticamente los ciclos de turnos (7x7, 14x7, etc.)
    
    FLUJO DE PROCESAMIENTO:
    1. Obtener parámetros (mes, año, personas)
    2. Cargar datos de licencias médicas y ausentismos
    3. Aplicar asignaciones de faena (ESTADO BASE)
    4. Calcular días de trabajo y descanso según turnos
    5. Aplicar licencias médicas (prioridad alta)
    6. Aplicar ausentismos (vacaciones, permisos, etc.)
    7. Ordenar estados por prioridad visual
    
    SISTEMA DE PRIORIDADES:
    - Prioridad 1: Estados base (disponible, en faena, descanso)
    - Prioridad 2: Estados secundarios (turno, vacaciones, permiso)
    - Prioridad 3: Estados de alta prioridad (licencia médica)
    
    Parámetros de entrada:
    - month: Mes del año (1-12)
    - year: Año (ej: 2025)
    - personas[]: Lista de IDs de personas a consultar
    
    Retorna: JSON con estados de cada persona para cada día del mes
    """
    
    # =============================================================================
    # OBTENER PARÁMETROS DE ENTRADA
    # =============================================================================
    
    month = int(request.GET.get('month'))
    year = int(request.GET.get('year'))
    persona_ids = request.GET.getlist('personas[]') or request.GET.get('personas', '')
    if isinstance(persona_ids, str) and persona_ids:
        persona_ids = [pid for pid in persona_ids.split(',') if pid]
    days_in_month = monthrange(year, month)[1]

    # Debug: imprimir los IDs recibidos
    print(f"DEBUG: persona_ids recibidos: {persona_ids}")
    print(f"DEBUG: month: {month}, year: {year}, days_in_month: {days_in_month}")

    # =============================================================================
    # PRELOAD DE DATOS PRINCIPALES
    # =============================================================================
    
    # Obtener objetos de Personal para las personas especificadas
    personas = Personal.objects.filter(personal_id__in=persona_ids)

    # =============================================================================
    # CARGAR LICENCIAS MÉDICAS DEL MES
    # =============================================================================
    
    # Obtener licencias médicas que se superponen con el mes consultado
    licencias = (
        LicenciaMedicaPorPersonal.objects
        .filter(
            personal_id__in=personas,
            fechaEmision__lte=date(year, month, days_in_month),
            fecha_fin_licencia__gte=date(year, month, 1),
        )
        .values('personal_id', 'fechaEmision', 'fecha_fin_licencia')
    )

    # =============================================================================
    # CARGAR AUSENTISMOS DEL MES
    # =============================================================================
    
    # Obtener ausentismos (vacaciones, permisos, etc.) que se superponen con el mes
    ausentismos = (
        Ausentismo.objects
        .filter(
            personal_id__in=personas,
            fechaini__lte=date(year, month, days_in_month),
            fechafin__gte=date(year, month, 1),
        )
        .values('personal_id', 'fechaini', 'fechafin', 'tipoausen_id__tipo')
    )

    # =============================================================================
    # INICIALIZAR MAPA DE ESTADOS
    # =============================================================================
    
    # Crear estructura de datos: persona -> día -> lista de estados
    results = {}
    for p in personas:
        results[str(p.personal_id)] = {str(d): [] for d in range(1, days_in_month + 1)}

    # =============================================================================
    # FUNCIÓN AUXILIAR PARA ITERAR DÍAS
    # =============================================================================
    
    # Helper para iterar sobre un rango de días respetando límites del mes
    def iter_days(start, end):
        from datetime import timedelta
        current = max(start, date(year, month, 1))
        last = min(end, date(year, month, days_in_month))
        while current <= last:
            yield current.day
            current += timedelta(days=1)

    # =============================================================================
    # APLICAR ASIGNACIONES DE FAENA (ESTADO BASE)
    # =============================================================================

    # Consulta optimizada para obtener todas las asignaciones de faena del mes
    # Incluye información de turnos tanto de la persona como de la faena
    asignaciones_faena = (
        PersonalFaena.objects
        .filter(
            personal_id__in=personas,
            activo=True,
            fecha_inicio__lte=date(year, month, days_in_month)
        )
        .select_related('faena', 'tipo_turno', 'faena__tipo_turno')
        .values('personal_id', 'faena_id', 'faena__nombre', 'fecha_inicio', 'faena__fecha_fin', 'tipo_turno__dias_trabajo', 
                'tipo_turno__dias_descanso', 'faena__tipo_turno__dias_trabajo', 
                'faena__tipo_turno__dias_descanso', 'faena__tipo_turno__nombre')
    )
    
    # =============================================================================
    # INICIALIZAR MAPAS DE DÍAS EN FAENA Y DESCANSO
    # =============================================================================
    
    # Diccionarios para almacenar qué días cada persona está en faena o descanso
    dias_en_faena = {}
    dias_de_descanso = {}
    
    print(f"DEBUG: asignaciones_faena encontradas: {len(asignaciones_faena)}")
    for a in asignaciones_faena:
        print(f"DEBUG: Asignación - Personal: {a['personal_id']}, Faena: {a['faena__nombre']}, Fecha inicio: {a['fecha_inicio']}, Fecha fin faena: {a['faena__fecha_fin']}")
    
    # =============================================================================
    # PROCESAR CADA ASIGNACIÓN DE FAENA
    # =============================================================================
    
    for a in asignaciones_faena:
        personal_id_str = str(a['personal_id'])
        
        # Inicializar conjunto de días para esta persona si no existe
        if personal_id_str not in dias_en_faena:
            dias_en_faena[personal_id_str] = set()
        
        # =============================================================================
        # LÓGICA DE CÁLCULO DE TURNOS
        # =============================================================================
        
        # Obtener el turno específico de la persona o usar el de la faena
        # Si la persona tiene turno específico, se usa ese; si no, se usa el de la faena
        dias_trabajo = a['tipo_turno__dias_trabajo'] or a['faena__tipo_turno__dias_trabajo']
        dias_descanso = a['tipo_turno__dias_descanso'] or a['faena__tipo_turno__dias_descanso']
        
        if dias_trabajo and dias_descanso:
            print(f"DEBUG: Personal {personal_id_str} tiene turno {dias_trabajo}x{dias_descanso}")
            
            # =============================================================================
            # CÁLCULO DE CICLOS DE TURNO
            # =============================================================================
            
            # Calcular el ciclo completo del turno (trabajo + descanso)
            duracion_ciclo = dias_trabajo + dias_descanso
            
            # Obtener la fecha fin de la faena para limitar los turnos
            fecha_fin_faena = a['faena__fecha_fin']
            if fecha_fin_faena:
                print(f"DEBUG: Personal {personal_id_str} - Faena termina el {fecha_fin_faena}")
            
            # =============================================================================
            # CALCULAR DÍAS DE TRABAJO Y DESCANSO PARA CADA DÍA DEL MES
            # =============================================================================
            
            # Para cada día del mes, determinar si está en trabajo o descanso
            print(f"DEBUG: Personal {personal_id_str} - Calculando días para mes {month}/{year}, faena termina: {fecha_fin_faena}")
            for d in range(1, days_in_month + 1):
                fecha_actual = date(year, month, d)
                
                # =============================================================================
                # RESPETAR FECHA FIN DE FAENA
                # =============================================================================
                
                # Verificar que la fecha actual no sobrepase la fecha fin de la faena
                if fecha_fin_faena and fecha_actual > fecha_fin_faena:
                    print(f"DEBUG: Personal {personal_id_str} - Día {d} ({fecha_actual}) sobrepasa fecha fin de faena ({fecha_fin_faena}) - SALTANDO")
                    continue
                
                # =============================================================================
                # CALCULAR POSICIÓN EN EL CICLO DE TURNO
                # =============================================================================
                
                # Calcular cuántos días han pasado desde el inicio de la asignación
                dias_desde_inicio_actual = (fecha_actual - a['fecha_inicio']).days
                
                if dias_desde_inicio_actual >= 0:  # Solo días futuros al inicio de la asignación
                    # Calcular en qué posición del ciclo está este día
                    dia_en_ciclo_actual = dias_desde_inicio_actual % duracion_ciclo
                    
                    if dia_en_ciclo_actual < dias_trabajo:
                        # Está en días de trabajo - agregar a días en faena
                        dias_en_faena[personal_id_str].add(d)
                    else:
                        # Está en días de descanso - agregar a días de descanso
                        if personal_id_str not in dias_de_descanso:
                            dias_de_descanso[personal_id_str] = set()
                        dias_de_descanso[personal_id_str].add(d)
            
            # Debug: mostrar resultados del cálculo
            print(f"DEBUG: Personal {personal_id_str} - Días en faena: {sorted(dias_en_faena[personal_id_str])}")
            print(f"DEBUG: Personal {personal_id_str} - Días de descanso: {sorted(dias_de_descanso.get(personal_id_str, set()))}")
            
        else:
            print(f"DEBUG: Personal {personal_id_str} NO tiene turno definido")
            
            # =============================================================================
            # CASO SIN TURNO DEFINIDO
            # =============================================================================
            
            # Si no hay turno definido, asumir que está en faena todos los días
            # Pero respetar la fecha fin de la faena
            fecha_fin = a['fecha_inicio'] + timedelta(days=30)
            if a['faena__fecha_fin']:
                fecha_fin = min(fecha_fin, a['faena__fecha_fin'])
            fecha_fin = min(date(year, month, days_in_month), fecha_fin)
            
            print(f"DEBUG: Personal {personal_id_str} - Fecha fin calculada: {fecha_fin}")
            
            # Agregar todos los días desde inicio hasta fin como días en faena
            for d in iter_days(a['fecha_inicio'], fecha_fin):
                dias_en_faena[personal_id_str].add(d)
    
    # Aplicar estados múltiples por día
    for pid, days in results.items():
        for d, estados in days.items():
            day_num = int(d)
            
            # Verificar si la persona está en faena en este día
            en_faena = pid in dias_en_faena and day_num in dias_en_faena[pid]
            
            # Si está en faena, agregar el estado base
            if en_faena:
                # Buscar el nombre de la faena para este día
                faena_nombre = "Faena"
                for a in asignaciones_faena:
                    if str(a['personal_id']) == pid:
                        fecha_inicio = a['fecha_inicio']
                        # Respetar la fecha fin de la faena
                        fecha_fin = fecha_inicio + timedelta(days=30)
                        if a['faena__fecha_fin']:
                            fecha_fin = min(fecha_fin, a['faena__fecha_fin'])
                        fecha_fin = min(date(year, month, days_in_month), fecha_fin)
                        
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            faena_nombre = a['faena__nombre']
                            break
                
                # Buscar información detallada de la faena para este día
                faena_info = None
                for a in asignaciones_faena:
                    if str(a['personal_id']) == pid:
                        fecha_inicio = a['fecha_inicio']
                        # Calcular fecha fin basándose en el turno o usar un límite razonable
                        # Pero respetar la fecha fin de la faena
                        if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso']:
                            # Si hay turno, calcular fecha fin basándose en el turno
                            dias_ciclo = a['tipo_turno__dias_trabajo'] + a['tipo_turno__dias_descanso']
                            fecha_fin = fecha_inicio + timedelta(days=dias_ciclo * 3)  # 3 ciclos como máximo
                        else:
                            # Si no hay turno, usar un límite de 30 días
                            fecha_fin = fecha_inicio + timedelta(days=30)
                        
                        # Respetar la fecha fin de la faena si está definida
                        if a['faena__fecha_fin']:
                            fecha_fin = min(fecha_fin, a['faena__fecha_fin'])
                        
                        fecha_fin = min(date(year, month, days_in_month), fecha_fin)
                        
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            # Formatear fecha en español
                            fecha_inicio_str = a['fecha_inicio'].strftime('%d de %B de %Y') if a['fecha_inicio'] else 'No especificada'
                            faena_info = {
                                'faena_id': a['faena_id'],
                                'faena_nombre': a['faena__nombre'],
                                'fecha_inicio': fecha_inicio_str,
                                'turno': f"{a['tipo_turno__dias_trabajo']}x{a['tipo_turno__dias_descanso']}" if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso'] else a['faena__tipo_turno__nombre'] or 'Turno no especificado'
                            }
                            break
                
                estados.append({
                    'tipo': 'en_faena',
                    'color': 'celeste',
                    'texto': 'Faena',
                    'prioridad': 1,  # Prioridad baja para estado base
                    'detalles': faena_info
                })
            
            # Si no está en faena, está disponible (pero esto puede cambiar después)
            if not en_faena:
                estados.append({
                    'tipo': 'disponible',
                    'color': 'gris',
                    'texto': 'Disp',
                    'prioridad': 1
                })
    
    # Aplicar descanso del turno (estado base)
    for pid, days in results.items():
        for d, estados in days.items():
            day_num = int(d)
            
            # Verificar si la persona está en descanso del turno en este día
            en_descanso_turno = pid in dias_de_descanso and day_num in dias_de_descanso[pid]
            
            if en_descanso_turno:
                # Buscar información de la faena para el descanso
                faena_info = None
                for a in asignaciones_faena:
                    if str(a['personal_id']) == pid:
                        fecha_inicio = a['fecha_inicio']
                        # Calcular fecha fin basándose en el turno o usar un límite razonable
                        # Pero respetar la fecha fin de la faena
                        if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso']:
                            # Si hay turno, calcular fecha fin basándose en el turno
                            dias_ciclo = a['tipo_turno__dias_trabajo'] + a['tipo_turno__dias_descanso']
                            fecha_fin = fecha_inicio + timedelta(days=dias_ciclo * 3)  # 3 ciclos como máximo
                        else:
                            # Si no hay turno, usar un límite de 30 días
                            fecha_fin = fecha_inicio + timedelta(days=30)
                        
                        # Respetar la fecha fin de la faena si está definida
                        if a['faena__fecha_fin']:
                            fecha_fin = min(fecha_fin, a['faena__fecha_fin'])
                        
                        fecha_fin = min(date(year, month, days_in_month), fecha_fin)
                        
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            # Formatear fecha en español
                            fecha_inicio_str = a['fecha_inicio'].strftime('%d de %B de %Y') if a['fecha_inicio'] else 'No especificada'
                            faena_info = {
                                'faena_id': a['faena_id'],
                                'faena_nombre': a['faena__nombre'],
                                'fecha_inicio': fecha_inicio_str,
                                'turno': f"{a['tipo_turno__dias_trabajo']}x{a['tipo_turno__dias_descanso']}" if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso'] else a['faena__tipo_turno__nombre'] or 'Turno no especificado'
                            }
                            break
                
                estados.append({
                    'tipo': 'descanso',
                    'color': 'verde',
                    'texto': 'Descanso',
                    'prioridad': 1,  # Prioridad alta (estado base)
                    'detalles': faena_info
                })
                
                # Remover estado "disponible" si existe (el descanso tiene prioridad)
                estados[:] = [estado for estado in estados if estado['tipo'] != 'disponible']
    
    # Aplicar turnos (se superponen a la faena)
    # Placeholder: En un sistema real, se conectaría con tabla de turnos
    for pid, days in results.items():
        for d, estados in days.items():
            day_num = int(d)
            
            # Verificar si la persona está en faena en este día
            en_faena = pid in dias_en_faena and day_num in dias_en_faena[pid]
            
            # Si está en faena, puede tener turno
            if en_faena:
                has_turno = False  # Reemplazar con lógica real después
                if has_turno:
                    estados.append({
                        'tipo': 'turno',
                        'color': 'orange',
                        'texto': 'Turno',
                        'prioridad': 2  # Prioridad media
                    })
    
    # Aplicar licencias médicas (se superponen a la faena y turno)
    for l in licencias:
        personal_id_str = str(l['personal_id'])
        if personal_id_str in results:
            for d in iter_days(l['fechaEmision'], l['fecha_fin_licencia']):
                if str(d) in results[personal_id_str]:
                    # Buscar información detallada de la licencia
                    # Formatear fechas en español
                    fecha_inicio_str = l['fechaEmision'].strftime('%d de %B de %Y') if l['fechaEmision'] else 'No especificada'
                    fecha_fin_str = l['fecha_fin_licencia'].strftime('%d de %B de %Y') if l['fecha_fin_licencia'] else 'No especificada'
                    licencia_info = {
                        'fecha_inicio': fecha_inicio_str,
                        'fecha_fin': fecha_fin_str,
                        'tipo': 'Licencia Médica'
                    }
                    
                    # Agregar licencia
                    results[personal_id_str][str(d)].append({
                        'tipo': 'licencia',
                        'color': 'salmon',
                        'texto': 'Licencia',
                        'prioridad': 3,  # Prioridad alta
                        'detalles': licencia_info
                    })
                    
                    # Remover estado "disponible" si existe (la licencia tiene prioridad)
                    results[personal_id_str][str(d)] = [
                        estado for estado in results[personal_id_str][str(d)] 
                        if estado['tipo'] != 'disponible'
                    ]
    
    # Aplicar ausentismos (se superponen a la faena)
    for a in ausentismos:
        personal_id_str = str(a['personal_id'])
        if personal_id_str in results:
            tipo = (a['tipoausen_id__tipo'] or '').lower()
            tag = None
            color = None
            if 'vacacion' in tipo:
                tag, color = 'vacaciones', 'amarillo'
            elif 'descanso' in tipo:
                tag, color = 'descanso', 'verde'
                # El descanso es un estado base (prioridad 1), no un ausentismo secundario
            elif 'permiso' in tipo:
                tag, color = 'permiso', 'naranjo'
            else:
                tag, color = 'ausencia', 'gris'
            
            for d in iter_days(a['fechaini'], a['fechafin']):
                if str(d) in results[personal_id_str]:
                    # Personalizar el texto según el tipo
                    if 'vacacion' in tipo:
                        texto_mostrar = 'Vac'
                    elif 'descanso' in tipo:
                        texto_mostrar = 'Descanso'
                    elif 'permiso' in tipo:
                        texto_mostrar = 'Perm'
                    else:
                        texto_mostrar = a['tipoausen_id__tipo']
                    
                    # Agregar el ausentismo
                    # El descanso es estado base (prioridad 1), los demás son secundarios (prioridad 2)
                    prioridad_estado = 1 if tag == 'descanso' else 2
                    
                    # Buscar información detallada del ausentismo
                    # Formatear fechas en español
                    fecha_inicio_str = a['fechaini'].strftime('%d de %B de %Y') if a['fechaini'] else 'No especificada'
                    fecha_fin_str = a['fechafin'].strftime('%d de %B de %Y') if a['fechafin'] else 'No especificada'
                    ausentismo_info = {
                        'fecha_inicio': fecha_inicio_str,
                        'fecha_fin': fecha_fin_str,
                        'tipo': a['tipoausen_id__tipo']
                    }
                    
                    results[personal_id_str][str(d)].append({
                        'tipo': tag,
                        'color': color,
                        'texto': texto_mostrar,
                        'prioridad': prioridad_estado,
                        'detalles': ausentismo_info
                    })
                    
                    # Remover estado "disponible" si existe (los ausentismos tienen prioridad)
                    results[personal_id_str][str(d)] = [
                        estado for estado in results[personal_id_str][str(d)] 
                        if estado['tipo'] != 'disponible'
                    ]

    # =============================================================================
    # ORDENAR ESTADOS POR PRIORIDAD Y PREPARAR RESPUESTA FINAL
    # =============================================================================
    
    # SISTEMA DE PRIORIDADES VISUALES:
    # Prioridad 1: Estados base (disponible, en faena, descanso) - Se muestran ARRIBA
    # Prioridad 2: Estados secundarios (turno, vacaciones, permiso) - Se muestran ABAJO
    # Prioridad 3: Estados de alta prioridad (licencia médica) - Se muestran AL FINAL
    # 
    # IMPORTANTE: El estado "disponible" se remueve automáticamente cuando hay otros estados
    # porque no puede coexistir con licencia, descanso, permiso, vacaciones, etc.
    
    for pid, days in results.items():
        for d, estados in days.items():
            # =============================================================================
            # ORDENAR ESTADOS POR PRIORIDAD VISUAL
            # =============================================================================
            
            # Ordenar estados por prioridad (menor número = mayor prioridad visual)
            # Esto determina el orden en que se muestran los estados en el calendario
            estados.sort(key=lambda x: x['prioridad'])
            
            # Debug: mostrar el orden final de estados para cada día
            if estados:
                print(f"DEBUG: Persona {pid}, Día {d} - Estados ordenados: {[estado['tipo'] for estado in estados]}")

    # =============================================================================
    # DEBUG: IMPRIMIR RESULTADO FINAL
    # =============================================================================
    
    # Debug: imprimir el resultado completo para verificación
    print(f"DEBUG: resultados para {len(results)} personas")
    for pid, days in results.items():
        print(f"  Persona {pid}: {len([d for d in days.values() if d])} días con estados")
        # Mostrar algunos ejemplos de estados (solo primeros 3 días para no saturar)
        for day, estados in list(days.items())[:3]:  # Solo primeros 3 días
            if estados:
                print(f"    Día {day}: {estados}")

    # =============================================================================
    # RETORNAR RESPUESTA JSON AL FRONTEND
    # =============================================================================
    
    # Retornar el mapa completo de estados para todas las personas y días
    return JsonResponse({'results': results})


# =============================================================================
# API PARA OBTENER TURNOS
# =============================================================================

@require_GET
def get_turnos(request):
    """
    Obtener lista de turnos disponibles en el sistema
    
    Esta función proporciona la lista de turnos para las asignaciones:
    - Obtiene todos los turnos activos (7x7, 14x7, etc.)
    - Se usa al asignar personal a faenas
    - Incluye debug logs para troubleshooting
    
    Retorna: JSON con lista de turnos activos
    """
    try:
        print(f"DEBUG: get_turnos - Iniciando...")
        
        # Obtener todos los turnos activos ordenados por nombre
        turnos = TipoTurno.objects.filter(activo=True).values('tipo_turno_id', 'nombre').order_by('nombre')
        print(f"DEBUG: get_turnos - Query ejecutada, {turnos.count()} turnos encontrados")
        
        # Convertir QuerySet a lista para mejor manejo
        turnos_list = list(turnos)
        print(f"DEBUG: get_turnos - Turnos convertidos a lista: {turnos_list}")
        
        # Construir respuesta final
        response_data = {'results': turnos_list}
        print(f"DEBUG: get_turnos - Respuesta final: {response_data}")
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"ERROR en get_turnos: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


# =============================================================================
# API PARA OBTENER INFORMACIÓN DE FAENA Y TURNO
# =============================================================================

@require_GET
def get_faena_turno(request, faena_id):
    """
    Obtener el turno y fechas de una faena específica
    
    Esta función se usa para obtener información detallada de una faena:
    - Obtiene el turno asignado a la faena
    - Incluye fechas de inicio y fin de la faena
    - Se usa para validaciones en el frontend
    
    Parámetros:
    - faena_id: ID de la faena a consultar
    
    Retorna: JSON con información de turno y fechas de la faena
    """
    try:
        # Obtener la faena específica
        faena = Faena.objects.get(faena_id=faena_id)
        
        # Información del turno (puede ser None si no tiene turno asignado)
        turno_info = faena.tipo_turno.nombre if faena.tipo_turno else 'No especificado'
        
        # Información de fechas en formato dd/mm/yyyy
        fecha_inicio = faena.fecha_inicio.strftime('%d/%m/%Y') if faena.fecha_inicio else 'No especificada'
        fecha_fin = faena.fecha_fin.strftime('%d/%m/%Y') if faena.fecha_fin else 'No especificada'
        
        # Construir respuesta con toda la información
        return JsonResponse({
            'success': True, 
            'turno': turno_info,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'nombre_faena': faena.nombre
        })
        
    except Faena.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Faena no encontrada'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# =============================================================================
# API PARA ASIGNAR PERSONAL A FAENAS
# =============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


@csrf_exempt
@require_POST
def assign_personal_to_faena(request):
    """
    ASIGNAR PERSONAL A UNA FAENA ESPECÍFICA
    
    Esta función es el corazón del sistema de asignación de personal:
    - Permite asignar personal a faenas con fechas específicas
    - Valida que las fechas estén dentro del rango de la faena
    - Verifica que los turnos no sobrepasen la fecha fin de la faena
    - Maneja tanto nuevas asignaciones como ediciones
    - Crea logs de auditoría para todas las operaciones
    
    FLUJO DE VALIDACIÓN:
    1. Validar que la fecha de inicio esté dentro del rango de la faena
    2. Si hay turno, verificar que no sobrepase la fecha fin de la faena
    3. Calcular ciclos de turno y validar duración total
    
    FLUJO DE ASIGNACIÓN:
    1. Verificar si ya existe una asignación para la misma fecha
    2. Si existe, actualizar; si no, crear nueva
    3. Desactivar otras asignaciones activas a la misma faena
    4. Crear log de auditoría con todos los cambios
    
    Parámetros de entrada:
    - personal_id: ID de la persona a asignar
    - faena_id: ID de la faena destino
    - turno_id: ID del turno (opcional)
    - fecha_inicio: Fecha de inicio de la asignación (YYYY-MM-DD)
    - is_editing: Boolean indicando si es edición o nueva asignación
    
    Retorna: JSON con resultado de la operación
    """
    try:
        print(f"DEBUG: assign_personal_to_faena - Request body: {request.body}")
        print(f"DEBUG: Request method: {request.method}")
        print(f"DEBUG: Request content type: {request.content_type}")
        
        # Verificar que el request tenga contenido
        if not request.body:
            print("DEBUG: Request body está vacío")
            return JsonResponse({'success': False, 'error': 'Request body vacío'})
        
        # Intentar parsear como JSON primero, si falla, usar datos de formulario
        try:
            data = json.loads(request.body)
            print(f"DEBUG: Datos parseados como JSON: {data}")
        except json.JSONDecodeError:
            # Si no es JSON, usar datos de formulario
            print(f"DEBUG: Parseando como datos de formulario...")
            data = {}
            if request.content_type == 'application/x-www-form-urlencoded':
                # Parsear datos de formulario
                from urllib.parse import parse_qs
                form_data = parse_qs(request.body.decode('utf-8'))
                data = {key: value[0] if value else None for key, value in form_data.items()}
                print(f"DEBUG: Datos parseados como formulario: {data}")
            else:
                print(f"DEBUG: Content type no reconocido: {request.content_type}")
                return JsonResponse({'success': False, 'error': 'Formato de datos no soportado'})
        
        personal_id = data.get('personal_id')
        faena_id = data.get('faena_id')
        turno_id = data.get('turno_id')
        fecha_inicio = data.get('fecha_inicio')
        is_editing = data.get('is_editing', False)
        
        print(f"DEBUG: personal_id: {personal_id}, faena_id: {faena_id}, turno_id: {turno_id}, fecha_inicio: {fecha_inicio}")
        print(f"DEBUG: Modo: {'Edición' if is_editing else 'Nueva asignación'}")
        print(f"DEBUG: Tipo de is_editing: {type(is_editing)}, Valor: {is_editing}")
        print(f"DEBUG: is_editing es True?: {is_editing == True}")
        print(f"DEBUG: is_editing es False?: {is_editing == False}")
        print(f"DEBUG: is_editing == 'true'?: {is_editing == 'true'}")
        print(f"DEBUG: is_editing == 'false'?: {is_editing == 'false'}")
        print(f"DEBUG: is_editing == 1?: {is_editing == 1}")
        print(f"DEBUG: is_editing == 0?: {is_editing == 0}")
        print(f"DEBUG: Tipo de personal_id: {type(personal_id)}")
        print(f"DEBUG: Tipo de faena_id: {type(faena_id)}")
        print(f"DEBUG: Tipo de turno_id: {type(turno_id)}")
        print(f"DEBUG: Tipo de fecha_inicio: {type(fecha_inicio)}")
        
        if not all([personal_id, faena_id, fecha_inicio]):
            print(f"DEBUG: Faltan datos requeridos - personal_id: {personal_id}, faena_id: {faena_id}, fecha_inicio: {fecha_inicio}")
            return JsonResponse({'success': False, 'error': 'Faltan datos requeridos'})
        
        # Convertir a enteros si es necesario
        try:
            personal_id = int(personal_id)
            faena_id = int(faena_id)
            if turno_id:
                turno_id = int(turno_id)
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Error al convertir IDs: {e}")
            return JsonResponse({'success': False, 'error': 'IDs inválidos'})
        
        print(f"DEBUG: IDs convertidos - personal_id: {personal_id}, faena_id: {faena_id}, turno_id: {turno_id}")
        
        # Normalizar el valor de is_editing para manejar strings y booleanos
        if isinstance(is_editing, str):
            is_editing = is_editing.lower() in ['true', '1', 'yes']
        elif isinstance(is_editing, int):
            is_editing = bool(is_editing)
        
        print(f"DEBUG: is_editing normalizado: {is_editing} (tipo: {type(is_editing)})")
        
        # Validaciones adicionales antes de procesar
        try:
            # Obtener la faena para validaciones
            faena = Faena.objects.get(faena_id=faena_id)
            personal = Personal.objects.get(personal_id=personal_id)
            
            # Convertir fecha_inicio a objeto date
            from datetime import datetime
            fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            
            # Validar que la fecha de inicio esté dentro del rango de la faena
            if fecha_inicio_obj < faena.fecha_inicio:
                return JsonResponse({
                    'success': False, 
                    'error': f'La fecha de inicio ({fecha_inicio_obj.strftime("%d/%m/%Y")}) no puede ser anterior al inicio de la faena ({faena.fecha_inicio.strftime("%d/%m/%Y")})'
                })
            
            if faena.fecha_fin and fecha_inicio_obj > faena.fecha_fin:
                return JsonResponse({
                    'success': False, 
                    'error': f'La fecha de inicio ({fecha_inicio_obj.strftime("%d/%m/%Y")}) no puede ser posterior al fin de la faena ({faena.fecha_fin.strftime("%d/%m/%Y")})'
                })
            
            # Validar que si hay turno, los turnos no sobrepasen la fecha fin de la faena
            if turno_id and faena.fecha_fin:
                tipo_turno = TipoTurno.objects.get(tipo_turno_id=turno_id)
                
                # Calcular cuántos ciclos completos puede hacer la persona
                dias_disponibles = (faena.fecha_fin - fecha_inicio_obj).days + 1
                ciclos_completos = dias_disponibles // tipo_turno.duracion_ciclo
                dias_trabajo_total = ciclos_completos * tipo_turno.dias_trabajo
                
                # La fecha fin será inicio + días de trabajo
                fecha_fin_calculada = fecha_inicio_obj + timedelta(days=dias_trabajo_total - 1)
                
                if fecha_fin_calculada > faena.fecha_fin:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Los turnos asignados se extienden más allá de la fecha de fin de la faena. '
                                f'La asignación terminaría el {fecha_fin_calculada.strftime("%d/%m/%Y")} pero la faena termina el {faena.fecha_fin.strftime("%d/%m/%Y")}. '
                                f'Considere ajustar la fecha de inicio o el turno.'
                    })
                    
        except (Faena.DoesNotExist, Personal.DoesNotExist, TipoTurno.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': f'Error al obtener datos: {str(e)}'})
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Error en formato de fecha: {str(e)}'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Error en validación: {str(e)}'})
        
        if is_editing:
            # Modo edición: actualizar la asignación existente
            print(f"DEBUG: Modo edición - actualizando asignación existente...")
            try:
                asignacion_existente = PersonalFaena.objects.get(
                    personal_id=personal_id,
                    faena_id=faena_id,
                    activo=True
                )
                
                # Guardar datos anteriores para el log
                datos_anteriores = {
                    'tipo_turno_id': asignacion_existente.tipo_turno_id,
                    'fecha_inicio': asignacion_existente.fecha_inicio.strftime('%Y-%m-%d') if asignacion_existente.fecha_inicio else None
                }
                
                # Actualizar campos
                asignacion_existente.tipo_turno_id = turno_id
                asignacion_existente.fecha_inicio = fecha_inicio
                
                # Validar antes de guardar
                asignacion_existente.full_clean()
                asignacion_existente.save()
                
                # Crear log de auditoría para la edición
                try:
                    personal = Personal.objects.get(personal_id=personal_id)
                    faena = Faena.objects.get(faena_id=faena_id)
                    turno_anterior = TipoTurno.objects.get(tipo_turno_id=datos_anteriores['tipo_turno_id']).nombre if datos_anteriores['tipo_turno_id'] else 'Sin turno'
                    turno_nuevo = TipoTurno.objects.get(tipo_turno_id=turno_id).nombre if turno_id else 'Sin turno'
                    
                    descripcion = f"Se editó la asignación de {personal.nombre} {personal.apepat} en la faena '{faena.nombre}' - Turno: {turno_anterior} → {turno_nuevo}, Fecha: {datos_anteriores['fecha_inicio']} → {fecha_inicio}"
                    
                    AuditLog.crear_log(
                        accion='editar',
                        tabla_afectada='PersonalFaena',
                        registro_id=asignacion_existente.personal_faena_id,
                        descripcion=descripcion,
                        usuario=get_current_user_name(request),
                        datos_anteriores=datos_anteriores,
                        datos_nuevos={
                            'tipo_turno_id': turno_id,
                            'fecha_inicio': fecha_inicio,
                            'personal_rut': f"{personal.rut}-{personal.dvrut}"
                        },
                        ip_address=get_client_ip(request)
                    )
                    print(f"DEBUG: Log de auditoría para edición creado exitosamente")
                except Exception as e:
                    print(f"ERROR al crear log de auditoría para edición: {str(e)}")
                
                print(f"DEBUG: Asignación actualizada exitosamente")
                return JsonResponse({'success': True, 'assignment_id': asignacion_existente.personal_faena_id, 'message': 'Asignación actualizada'})
                
            except PersonalFaena.DoesNotExist:
                print(f"DEBUG: No se encontró asignación existente para editar")
                return JsonResponse({'success': False, 'error': 'No se encontró asignación existente para editar'})
        else:
            # Modo nueva asignación: crear nueva
            print(f"DEBUG: Modo nueva asignación - creando nueva asignación...")
            
            # Verificar si ya existe una asignación activa a la misma faena
            # Solo desactivar si es la misma faena, permitir múltiples faenas simultáneas
            print(f"DEBUG: Verificando asignaciones existentes...")
            asignaciones_existentes = PersonalFaena.objects.filter(
                personal_id=personal_id,
                faena_id=faena_id,
                activo=True
            )
            print(f"DEBUG: Asignaciones existentes encontradas: {asignaciones_existentes.count()}")
            
            # Verificar si ya existe una asignación con la misma fecha de inicio
            asignacion_misma_fecha = PersonalFaena.objects.filter(
                personal_id=personal_id,
                faena_id=faena_id,
                fecha_inicio=fecha_inicio
            ).first()
            
            if asignacion_misma_fecha:
                print(f"DEBUG: Ya existe una asignación con la misma fecha de inicio, actualizando...")
                # Actualizar la asignación existente
                asignacion_misma_fecha.tipo_turno_id = turno_id
                asignacion_misma_fecha.activo = True
                asignacion_misma_fecha.full_clean()
                asignacion_misma_fecha.save()
                
                nueva_asignacion = asignacion_misma_fecha
                print(f"DEBUG: Asignación existente actualizada exitosamente")
            else:
                # Desactivar asignaciones existentes a la misma faena
                if asignaciones_existentes.exists():
                    print(f"DEBUG: Desactivando asignaciones existentes...")
                    asignaciones_existentes.update(activo=False)
                    print(f"DEBUG: Asignaciones desactivadas exitosamente")
                
                # Crear nueva asignación
                print(f"DEBUG: Creando nueva asignación...")
                nueva_asignacion = PersonalFaena(
                    personal_id=personal_id,
                    faena_id=faena_id,
                    tipo_turno_id=turno_id,
                    fecha_inicio=fecha_inicio,
                    activo=True
                )
                
                # Validar antes de guardar
                nueva_asignacion.full_clean()
                nueva_asignacion.save()
                print(f"DEBUG: Nueva asignación creada exitosamente con ID: {nueva_asignacion.personal_faena_id}")
            
            # Crear log de auditoría
            try:
                # Obtener información del personal y faena para el log
                personal = Personal.objects.get(personal_id=personal_id)
                faena = Faena.objects.get(faena_id=faena_id)
                turno_info = f" (Turno: {nueva_asignacion.tipo_turno.nombre})" if nueva_asignacion.tipo_turno else ""
                
                descripcion = f"Se asignó a {personal.nombre} {personal.apepat} a la faena '{faena.nombre}' desde {fecha_inicio}{turno_info}"
                
                # Debug: mostrar exactamente qué datos se van a guardar
                datos_log = {
                    'personal_id': personal_id,
                    'personal_nombre': f"{personal.nombre} {personal.apepat}",
                    'personal_rut': f"{personal.rut}-{personal.dvrut}",
                    'faena_id': faena_id,
                    'faena_nombre': faena.nombre,
                    'fecha_inicio': fecha_inicio,
                    'turno_id': turno_id
                }
                print(f"DEBUG: Datos que se van a guardar en el log: {datos_log}")
                print(f"DEBUG: personal.rut = {personal.rut}, personal.dvrut = {personal.dvrut}")
                
                AuditLog.crear_log(
                    accion='asignar',
                    tabla_afectada='PersonalFaena',
                    registro_id=nueva_asignacion.personal_faena_id,
                    descripcion=descripcion,
                    usuario=get_current_user_name(request),
                    datos_nuevos=datos_log,
                    ip_address=get_client_ip(request)
                )
                print(f"DEBUG: Log de auditoría creado exitosamente")
            except Exception as e:
                print(f"ERROR al crear log de auditoría: {str(e)}")
            
            return JsonResponse({'success': True, 'assignment_id': nueva_asignacion.personal_faena_id, 'message': 'Nueva asignación creada'})
        
    except Exception as e:
        print(f"ERROR en assign_personal_to_faena: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def remove_personal_from_faena(request):
    """
    REMOVER PERSONAL DE UNA FAENA ESPECÍFICA O TODAS LAS FAENAS
    
    Esta función permite remover personal de faenas:
    - Si se especifica faena_id: remueve solo de esa faena
    - Si no se especifica: remueve de todas las faenas
    - Desactiva las asignaciones (no las elimina físicamente)
    - Crea logs de auditoría para todas las operaciones
    
    Parámetros de entrada:
    - personal_id: ID de la persona a remover
    - faena_id: ID de la faena específica (opcional)
    
    Retorna: JSON con resultado de la operación
    """
    try:
        print(f"DEBUG: remove_personal_from_faena - Request body: {request.body}")
        print(f"DEBUG: Request method: {request.method}")
        print(f"DEBUG: Request content type: {request.content_type}")
        
        # Verificar que el modelo PersonalFaena esté disponible
        print(f"DEBUG: Verificando importación del modelo PersonalFaena...")
        print(f"DEBUG: PersonalFaena: {PersonalFaena}")
        print(f"DEBUG: PersonalFaena.__module__: {PersonalFaena.__module__}")
        
        # Verificar que el request tenga contenido
        if not request.body:
            print("DEBUG: Request body está vacío")
            return JsonResponse({'success': False, 'error': 'Request body vacío'})
        
        # Intentar parsear como JSON primero, si falla, usar datos de formulario
        try:
            data = json.loads(request.body)
            print(f"DEBUG: Datos parseados como JSON: {data}")
        except json.JSONDecodeError:
            # Si no es JSON, usar datos de formulario
            print(f"DEBUG: Parseando como datos de formulario...")
            data = {}
            if request.content_type == 'application/x-www-form-urlencoded':
                # Parsear datos de formulario
                from urllib.parse import parse_qs
                form_data = parse_qs(request.body.decode('utf-8'))
                data = {key: value[0] if value else None for key, value in form_data.items()}
                print(f"DEBUG: Datos parseados como formulario: {data}")
            else:
                print(f"DEBUG: Content type no reconocido: {request.content_type}")
                return JsonResponse({'success': False, 'error': 'Formato de datos no soportado'})
        
        personal_id = data.get('personal_id')
        faena_id = data.get('faena_id')  # Nueva: faena específica a remover
        
        print(f"DEBUG: personal_id: {personal_id}, faena_id: {faena_id}")
        print(f"DEBUG: Tipo de personal_id: {type(personal_id)}")
        print(f"DEBUG: Tipo de faena_id: {type(faena_id)}")
        print(f"DEBUG: Data completo: {data}")
        
        # Validar que personal_id no sea None, vacío o 0
        if not personal_id or personal_id == '' or personal_id == 0:
            print(f"DEBUG: personal_id inválido: {personal_id}")
            return JsonResponse({'success': False, 'error': 'ID de personal requerido'})
        
        # Validar que faena_id sea válido si se proporciona
        if faena_id is not None and (faena_id == '' or faena_id == 0):
            print(f"DEBUG: faena_id inválido: {faena_id}")
            return JsonResponse({'success': False, 'error': 'ID de faena inválido'})
        
        # Convertir a enteros si es necesario
        try:
            personal_id = int(personal_id)
            if faena_id:
                faena_id = int(faena_id)
        except (ValueError, TypeError) as e:
            print(f"DEBUG: Error al convertir IDs: {e}")
            return JsonResponse({'success': False, 'error': 'IDs inválidos'})
        
        print(f"DEBUG: IDs convertidos - personal_id: {personal_id}, faena_id: {faena_id}")
        
        # Si se especifica una faena, remover solo esa
        if faena_id:
            print(f"DEBUG: Removiendo faena específica {faena_id} para personal {personal_id}")
            
            # Verificar que el modelo PersonalFaena existe
            print(f"DEBUG: Verificando modelo PersonalFaena...")
            print(f"DEBUG: PersonalFaena.objects: {PersonalFaena.objects}")
            
            # Construir la query paso a paso para debug
            print(f"DEBUG: Construyendo query...")
            query = PersonalFaena.objects.filter(activo=True)
            print(f"DEBUG: Query base (activo=True): {query.count()} resultados")
            
            query = query.filter(personal_id=personal_id)
            print(f"DEBUG: Query con personal_id={personal_id}: {query.count()} resultados")
            
            query = query.filter(faena_id=faena_id)
            print(f"DEBUG: Query final con faena_id={faena_id}: {query.count()} resultados")
            
            asignaciones = query
            
            if asignaciones.exists():
                print(f"DEBUG: Actualizando asignaciones...")
                
                # Crear logs de auditoría antes de desactivar
                for asignacion in asignaciones:
                    try:
                        personal = Personal.objects.get(personal_id=asignacion.personal_id)
                        faena = Faena.objects.get(faena_id=asignacion.faena_id)
                        turno_info = f" (Turno: {asignacion.tipo_turno.nombre})" if asignacion.tipo_turno else ""
                        
                        descripcion = f"Se removió a {personal.nombre} {personal.apepat} de la faena '{faena.nombre}'{turno_info}"
                        
                        AuditLog.crear_log(
                            accion='remover',
                            tabla_afectada='PersonalFaena',
                            registro_id=asignacion.personal_faena_id,
                            descripcion=descripcion,
                            usuario=get_current_user_name(request),
                            datos_anteriores={
                                'personal_id': asignacion.personal_id,
                                'personal_rut': f"{personal.rut}-{personal.dvrut}",
                                'faena_id': asignacion.faena_id,
                                'tipo_turno_id': asignacion.tipo_turno_id,
                                'fecha_inicio': asignacion.fecha_inicio.strftime('%Y-%m-%d') if asignacion.fecha_inicio else None,
                                'activo': True
                            },
                            ip_address=get_client_ip(request)
                        )
                    except Exception as e:
                        print(f"ERROR al crear log de auditoría para remoción: {str(e)}")
                
                asignaciones.update(activo=False)
                print(f"DEBUG: Asignaciones actualizadas exitosamente")
                return JsonResponse({'success': True, 'message': f'Personal removido de la faena {faena_id}'})
            else:
                print(f"DEBUG: No se encontraron asignaciones activas")
                return JsonResponse({'success': False, 'error': f'No se encontró asignación activa a la faena {faena_id}'})
        else:
            print(f"DEBUG: Removiendo todas las faenas para personal {personal_id}")
            
            # Si no se especifica faena, remover todas las asignaciones activas (comportamiento anterior)
            asignaciones = PersonalFaena.objects.filter(
                personal_id=personal_id,
                activo=True
            )
            
            print(f"DEBUG: Total asignaciones activas encontradas: {asignaciones.count()}")
            
            if asignaciones.exists():
                print(f"DEBUG: Actualizando todas las asignaciones...")
                
                # Crear logs de auditoría antes de desactivar
                for asignacion in asignaciones:
                    try:
                        personal = Personal.objects.get(personal_id=asignacion.personal_id)
                        faena = Faena.objects.get(faena_id=asignacion.faena_id)
                        turno_info = f" (Turno: {asignacion.tipo_turno_id})" if asignacion.tipo_turno_id else ""
                        
                        descripcion = f"Se removió a {personal.nombre} {personal.apepat} de la faena '{faena.nombre}'{turno_info}"
                        
                        AuditLog.crear_log(
                            accion='remover',
                            tabla_afectada='PersonalFaena',
                            registro_id=asignacion.personal_faena_id,
                            descripcion=descripcion,
                            usuario=get_current_user_name(request),
                            datos_anteriores={
                                'personal_id': asignacion.personal_id,
                                'personal_rut': f"{personal.rut}-{personal.dvrut}",
                                'faena_id': asignacion.faena_id,
                                'tipo_turno_id': asignacion.tipo_turno_id,
                                'fecha_inicio': asignacion.fecha_inicio.strftime('%Y-%m-%d') if asignacion.fecha_inicio else None,
                                'activo': True
                            },
                            ip_address=get_client_ip(request)
                        )
                    except Exception as e:
                        print(f"ERROR al crear log de auditoría para remoción: {str(e)}")
                
                asignaciones.update(activo=False)
                print(f"DEBUG: Todas las asignaciones actualizadas exitosamente")
                return JsonResponse({'success': True, 'message': 'Personal removido de todas las faenas'})
            else:
                print(f"DEBUG: No se encontraron asignaciones activas")
                return JsonResponse({'success': False, 'error': 'No se encontró asignación activa'})
        
    except Exception as e:
        print(f"ERROR en remove_personal_from_faena: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
def get_audit_logs(request):
    """
    OBTENER LOGS DE AUDITORÍA PARA MOSTRAR EN EL PANEL LATERAL
    
    Esta función proporciona acceso a todos los logs de auditoría del sistema:
    - Registra todas las acciones realizadas en el sistema
    - Permite filtrar por tipo de acción, tabla, usuario, personal y faena
    - Incluye información detallada de cada cambio
    - Se usa para rastrear quién hizo qué y cuándo
    
    SISTEMA DE FILTRADO:
    - accion: Filtrar por tipo de acción (asignar, remover, editar)
    - tabla: Filtrar por tabla afectada (PersonalFaena, Personal, etc.)
    - usuario: Filtrar por usuario que realizó el cambio
    - personal: Filtrar por nombre o RUT del personal afectado
    - faena: Filtrar por nombre o ID de la faena afectada
    
    BÚSQUEDA INTELIGENTE:
    - Busca en campos JSON (datos_nuevos, datos_anteriores)
    - Busca en descripción del log
    - Combina múltiples criterios con lógica OR
    - Incluye búsqueda por RUT del personal
    
    Parámetros de entrada:
    - limit: Número máximo de logs a retornar (default: 50)
    - accion: Filtrar por tipo de acción
    - tabla: Filtrar por tabla afectada
    - usuario: Filtrar por usuario que realizó el cambio
    - personal: Filtrar por nombre o RUT del personal afectado
    - faena: Filtrar por nombre o ID de la faena afectada
    
    Retorna: JSON con lista de logs filtrados y ordenados por fecha
    """
    try:
        # Obtener parámetros de filtrado
        limit = int(request.GET.get('limit', 50))  # Límite de logs a mostrar
        accion = request.GET.get('accion', '')  # Filtrar por tipo de acción
        tabla = request.GET.get('tabla', '')  # Filtrar por tabla afectada
        usuario = request.GET.get('usuario', '')  # Filtrar por usuario que realizó el cambio
        personal_filter = request.GET.get('personal', '')  # Filtrar por nombre o RUT del personal afectado
        faena_filter = request.GET.get('faena', '')  # Filtrar por faena
        
        print(f"DEBUG: Parámetros recibidos - accion: {accion}, usuario: {usuario}, personal_filter: {personal_filter}, faena_filter: {faena_filter}")
        
        # Construir query base
        logs = AuditLog.objects.all()
        print(f"DEBUG: Total de logs antes de filtros: {logs.count()}")
        
        # Aplicar filtros si se especifican
        if accion:
            logs = logs.filter(accion__icontains=accion)
            print(f"DEBUG: Después de filtro de acción: {logs.count()}")
        if tabla:
            logs = logs.filter(tabla_afectada__icontains=tabla)
            print(f"DEBUG: Después de filtro de tabla: {logs.count()}")
        
        # Filtrar por usuario (quien realizó el cambio) - SOLO si se especifica explícitamente
        if usuario and usuario.strip():
            logs = logs.filter(usuario__icontains=usuario)
            print(f"DEBUG: Después de filtro de usuario: {logs.count()}")
        
        # Filtrar por personal (nombre o RUT del personal afectado)
        if personal_filter and personal_filter.strip():
            print(f"DEBUG: Aplicando filtro de personal: {personal_filter}")
            
            # Debug: mostrar algunos logs antes de filtrar para entender la estructura
            print(f"DEBUG: Estructura de logs antes de filtrar:")
            sample_logs = logs[:3]
            for i, log in enumerate(sample_logs):
                print(f"  Log {i+1}:")
                print(f"    - descripcion: '{log.descripcion}'")
                print(f"    - datos_nuevos: {log.datos_nuevos}")
                print(f"    - datos_anteriores: {log.datos_anteriores}")
                if log.datos_nuevos:
                    print(f"    - personal_nombre en datos_nuevos: {log.datos_nuevos.get('personal_nombre', 'N/A')}")
                    print(f"    - personal_rut en datos_nuevos: {log.datos_nuevos.get('personal_rut', 'N/A')}")
                if log.datos_anteriores:
                    print(f"    - personal_nombre en datos_anteriores: {log.datos_anteriores.get('personal_nombre', 'N/A')}")
                    print(f"    - personal_rut en datos_anteriores: {log.datos_anteriores.get('personal_rut', 'N/A')}")
            
            # Usar un solo query que busque en todos los campos relevantes
            personal_q = Q(descripcion__icontains=personal_filter)
            personal_q |= Q(datos_nuevos__personal_nombre__icontains=personal_filter)
            personal_q |= Q(datos_nuevos__personal_rut__icontains=personal_filter)
            personal_q |= Q(datos_anteriores__personal_nombre__icontains=personal_filter)
            personal_q |= Q(datos_anteriores__personal_rut__icontains=personal_filter)
            
            # También buscar en cualquier parte de los datos JSON como fallback
            personal_q |= Q(datos_nuevos__icontains=personal_filter)
            personal_q |= Q(datos_anteriores__icontains=personal_filter)
            
            logs = logs.filter(personal_q)
            print(f"DEBUG: Total de logs después de filtro de personal: {logs.count()}")
            
            # Debug: mostrar algunos ejemplos de lo que se encontró
            if logs.count() > 0:
                print(f"DEBUG: Ejemplos de logs encontrados:")
                for i, log in enumerate(logs[:3]):
                    print(f"  Log {i+1}: descripcion='{log.descripcion}', datos_nuevos={log.datos_nuevos}")
            else:
                print(f"DEBUG: No se encontraron logs con el filtro: {personal_filter}")
                print(f"DEBUG: Intentando búsqueda más simple...")
                
                # Intentar búsqueda más simple solo en descripción
                simple_logs = logs.filter(descripcion__icontains=personal_filter)
                print(f"DEBUG: Logs encontrados solo en descripción: {simple_logs.count()}")
                
                if simple_logs.count() > 0:
                    print(f"DEBUG: Ejemplos de logs encontrados en descripción:")
                    for i, log in enumerate(simple_logs[:3]):
                        print(f"  Log {i+1}: descripcion='{log.descripcion}'")
        
        # Filtrar por faena
        if faena_filter and faena_filter.strip():
            print(f"DEBUG: Aplicando filtro de faena: {faena_filter}")
            # Buscar en todos los logs que puedan contener información de la faena
            # Incluir búsqueda en descripción y datos JSON
            faena_q = Q(descripcion__icontains=faena_filter)
            
            # Buscar en datos_nuevos y datos_anteriores JSON fields
            faena_q |= Q(datos_nuevos__faena_nombre__icontains=faena_filter)
            faena_q |= Q(datos_nuevos__faena_id__icontains=faena_filter)
            faena_q |= Q(datos_anteriores__faena_nombre__icontains=faena_filter)
            faena_q |= Q(datos_anteriores__faena_id__icontains=faena_filter)
            
            logs = logs.filter(faena_q)
            print(f"DEBUG: Después de filtro de faena: {logs.count()}")
        
        # Limitar resultados y ordenar por fecha más reciente
        logs = logs.order_by('-fecha_hora')[:limit]
        print(f"DEBUG: Logs finales después de límite: {len(logs)}")
        
        # Preparar datos para el frontend
        logs_data = []
        for log in logs:
            # Obtener información adicional del cargo si es una asignación de personal
            cargo_info = 'N/A'
            personal_info = 'N/A'
            faena_info = 'N/A'
            
            if log.tabla_afectada == 'PersonalFaena':
                try:
                    # Buscar la asignación para obtener el cargo
                    asignacion = PersonalFaena.objects.get(personal_faena_id=log.registro_id)
                    if asignacion.personal:
                        # Obtener el cargo más reciente del personal
                        ultimo_cargo = asignacion.personal.infolaboral_set.order_by('-fechacontrata').first()
                        if ultimo_cargo and ultimo_cargo.cargo_id:
                            cargo_info = ultimo_cargo.cargo_id.cargo
                        else:
                            cargo_info = 'Sin cargo asignado'
                        
                        # Información del personal
                        personal_info = f"{asignacion.personal.nombre} {asignacion.personal.apepat} ({asignacion.personal.rut}-{asignacion.personal.dvrut})"
                        
                        # Información de la faena
                        faena_info = asignacion.faena.nombre
                            
                except Exception as e:
                    print(f"Error obteniendo información para log {log.log_id}: {str(e)}")
                    cargo_info = 'Cargo no disponible'
                    personal_info = 'Personal no disponible'
                    faena_info = 'Faena no disponible'
            
            logs_data.append({
                'id': log.log_id,
                'usuario': log.usuario or 'Usuario Calendario',
                'accion': log.accion,
                'cargo': cargo_info,
                'personal': personal_info,
                'faena': faena_info,
                'descripcion': log.descripcion,
                'fecha_hora': timezone.localtime(log.fecha_hora).strftime('%d/%m/%Y %H:%M:%S'),
                'datos_anteriores': log.datos_anteriores,
                'datos_nuevos': log.datos_nuevos,
                'detalles_adicionales': log.descripcion
            })
        
        return JsonResponse({'success': True, 'logs': logs_data})
        
    except Exception as e:
        print(f"ERROR en get_audit_logs: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
