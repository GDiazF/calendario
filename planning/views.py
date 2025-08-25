from datetime import date
from calendar import monthrange
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.db.models import Q
from django.utils import timezone
import locale

# Configurar locale para fechas en español
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

from core.models import (
    Personal,
    Cargo,
    DeptoEmpresa,
    Empresa,
    Faena,
    TipoTurno,
    Ausentismo,
    LicenciaMedicaPorPersonal,
    PersonalFaena,
    AuditLog,
)


def get_client_ip(request):
    """Obtener la IP del cliente desde el request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_current_user_name(request):
    """Obtener el nombre del usuario actual autenticado"""
    if request.user.is_authenticated:
        if request.user.first_name and request.user.last_name:
            return f"{request.user.first_name} {request.user.last_name}"
        elif request.user.username:
            return request.user.username
        else:
            return request.user.email
    return 'Usuario no autenticado'


def calendar_view(request):
    """Vista principal del calendario de planificación"""
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


@require_GET
def get_personas(request):
    """Obtener lista de personas filtradas por faena y cargos"""
    # Intentar diferentes formas de obtener los cargos
    cargos_filter = request.GET.getlist('cargos')
    if not cargos_filter:
        cargos_filter = request.GET.getlist('cargos[]')
    if not cargos_filter:
        cargos_filter = request.GET.getlist('cargo_id')
    
    faena_id = request.GET.get('faena_id')
    
    # Debug: imprimir los parámetros recibidos
    print(f"DEBUG: cargos_filter recibido: {cargos_filter}")
    print(f"DEBUG: faena_id recibido: {faena_id}")
    print(f"DEBUG: request.GET completo: {dict(request.GET)}")
    print(f"DEBUG: request.GET.getlist('cargos'): {request.GET.getlist('cargos')}")
    print(f"DEBUG: request.GET.getlist('cargos[]'): {request.GET.getlist('cargos[]')}")
    print(f"DEBUG: request.GET.getlist('cargo_id'): {request.GET.getlist('cargo_id')}")
    
    # Debug: verificar todas las asignaciones a la faena seleccionada
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

    personas_qs = Personal.objects.filter(activo=True)
    print(f"DEBUG: Total de personal activo: {personas_qs.count()}")
    
    # Debug: verificar que la relación InfoLaboral funcione
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
    
    # Filtrar por cargos (usando InfoLaboral)
    if cargos_filter:
        print(f"DEBUG: Aplicando filtro de cargos: {cargos_filter}")
        # Filtrar por múltiples cargos usando Q objects para OR
        from django.db.models import Q
        cargo_filters = Q()
        for cargo_id in cargos_filter:
            cargo_filters |= Q(infolaboral__cargo_id=cargo_id)
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
    
    # Filtrar por faena (usando la nueva relación PersonalFaena)
    if faena_id:
        if faena_id == 'sin_asignar':
            print(f"DEBUG: Aplicando filtro 'SIN ASIGNAR'")
            # Filtrar personas que NO tienen faenas asignadas
            personas_qs = personas_qs.exclude(
                personalfaena__activo=True
            )
            print(f"DEBUG: Personas sin asignar: {personas_qs.count()}")
        else:
            print(f"DEBUG: Aplicando filtro de faena {faena_id}")
            personas_qs = personas_qs.filter(
                personalfaena__faena_id=faena_id,
                personalfaena__activo=True
            )
            print(f"DEBUG: Personas después del filtro de faena: {personas_qs.count()}")
        
        for persona in personas_qs:
            print(f"DEBUG: Persona {persona.personal_id} - {persona.nombre} {persona.apepat} - Pasa filtro de faena")

    personas_qs = personas_qs.distinct().select_related()

    # Obtener faenas actuales de forma eficiente (múltiples faenas por persona)
    faenas_actuales = {}
    cargos_actuales = {}
    from datetime import date
    today = date.today()
    
    # Si se filtra por faena específica, obtener solo esa faena
    if faena_id and faena_id != 'sin_asignar':
        asignaciones = PersonalFaena.objects.filter(
            personal_id__in=personas_qs,
            faena_id=faena_id,
            activo=True
        ).values('personal_id', 'faena__nombre', 'faena_id', 'fecha_inicio', 'tipo_turno__nombre')
    else:
        # Si no se filtra por faena o es 'sin_asignar', obtener todas las faenas activas de las personas
        asignaciones = PersonalFaena.objects.filter(
            personal_id__in=personas_qs,
            activo=True
        ).values('personal_id', 'faena__nombre', 'faena_id', 'fecha_inicio', 'tipo_turno__nombre')
    
    # Debug: imprimir las asignaciones
    print(f"DEBUG: Asignaciones encontradas: {list(asignaciones)}")
    
    # Agrupar múltiples faenas por persona
    for asignacion in asignaciones:
        personal_id = asignacion['personal_id']
        if personal_id not in faenas_actuales:
            faenas_actuales[personal_id] = []
        
        faenas_actuales[personal_id].append({
            'nombre': asignacion['faena__nombre'],
            'faena_id': asignacion['faena_id'],
            'fecha_inicio': asignacion['fecha_inicio'].isoformat() if asignacion['fecha_inicio'] else None,
            'turno': asignacion['tipo_turno__nombre'] or 'Sin turno específico'
        })
        print(f"DEBUG: Asignación para personal {personal_id}: {asignacion['faena__nombre']}")
    
    # Obtener cargos actuales de cada persona
    for persona in personas_qs:
        cargos = persona.infolaboral_set.values_list('cargo_id__cargo', flat=True)
        if cargos:
            cargos_actuales[persona.personal_id] = ', '.join(cargos)
        else:
            cargos_actuales[persona.personal_id] = 'Sin cargo'
        print(f"DEBUG: Cargo para personal {persona.personal_id}: {cargos_actuales[persona.personal_id]}")

    data = []
    for p in personas_qs:
        faenas_persona = faenas_actuales.get(p.personal_id, [])
        cargo_actual = cargos_actuales.get(p.personal_id, 'Sin cargo')
        
        # Para compatibilidad, mantener faena_actual como string (primera faena)
        faena_actual = faenas_persona[0]['nombre'] if faenas_persona else None
        
        data.append({
            'id': p.personal_id,
            'nombre': f"{p.nombre} {p.apepat} {p.apemat}",
            'rut': f"{p.rut}-{p.dvrut}",
            'faena_actual': faena_actual,
            'faenas_detalladas': faenas_persona,  # Nueva información detallada
            'cargo_actual': cargo_actual
        })
        # Debug: imprimir los datos de cada persona
        print(f"DEBUG: Persona {p.personal_id}: faena_actual = {faena_actual}, faenas_detalladas = {faenas_persona}, cargo_actual = {cargo_actual}")
    
    print(f"DEBUG: Datos enviados al frontend: {data}")
    return JsonResponse({'results': data})


@require_GET
def get_faenas(request):
    """Obtener lista de todas las faenas activas más opción 'Sin Asignar'"""
    
    faenas = Faena.objects.filter(
        activo=True
    ).values('faena_id', 'nombre', 'fecha_inicio', 'fecha_fin').order_by('nombre')
    
    data = [
        {
            'id': item['faena_id'], 
            'nombre': item['nombre'],
            'fecha_inicio': item['fecha_inicio'].strftime('%Y-%m-%d') if item['fecha_inicio'] else None,
            'fecha_fin': item['fecha_fin'].strftime('%Y-%m-%d') if item['fecha_fin'] else None
        } 
        for item in faenas
    ]
    
    # Agregar opción "SIN ASIGNAR" al final
    data.append({
        'id': 'sin_asignar',
        'nombre': 'SIN ASIGNAR',
        'fecha_inicio': None,
        'fecha_fin': None
    })
    
    return JsonResponse({'results': data})


@require_GET
def get_cargos(request):
    """Obtener todos los cargos disponibles"""
    cargos = Cargo.objects.all().values('cargo_id', 'cargo').order_by('cargo')
    data = [{'id': c['cargo_id'], 'nombre': c['cargo']} for c in cargos]
    return JsonResponse({'results': data})


@require_GET
def get_estados(request):
    """Obtener estados de personas para un mes específico"""
    month = int(request.GET.get('month'))
    year = int(request.GET.get('year'))
    persona_ids = request.GET.getlist('personas[]') or request.GET.get('personas', '')
    if isinstance(persona_ids, str) and persona_ids:
        persona_ids = [pid for pid in persona_ids.split(',') if pid]
    days_in_month = monthrange(year, month)[1]

    # Debug: imprimir los IDs recibidos
    print(f"DEBUG: persona_ids recibidos: {persona_ids}")
    print(f"DEBUG: month: {month}, year: {year}, days_in_month: {days_in_month}")

    # Preload data
    personas = Personal.objects.filter(personal_id__in=persona_ids)

    # Licencias medicas overlapping this month
    licencias = (
        LicenciaMedicaPorPersonal.objects
        .filter(
            personal_id__in=personas,
            fechaEmision__lte=date(year, month, days_in_month),
            fecha_fin_licencia__gte=date(year, month, 1),
        )
        .values('personal_id', 'fechaEmision', 'fecha_fin_licencia')
    )

    # Ausentismos para vacaciones/otros
    ausentismos = (
        Ausentismo.objects
        .filter(
            personal_id__in=personas,
            fechaini__lte=date(year, month, days_in_month),
            fechafin__gte=date(year, month, 1),
        )
        .values('personal_id', 'fechaini', 'fechafin', 'tipoausen_id__tipo')
    )

    # Build map per persona per day with multiple states
    results = {}
    for p in personas:
        results[str(p.personal_id)] = {str(d): [] for d in range(1, days_in_month + 1)}

    # Helpers
    def iter_days(start, end):
        from datetime import timedelta
        current = max(start, date(year, month, 1))
        last = min(end, date(year, month, days_in_month))
        while current <= last:
            yield current.day
            current += timedelta(days=1)

    # Los estados se aplicarán después de crear el mapa de días en faena

    # Aplicar asignaciones de faena (ESTADO BASE)
    asignaciones_faena = (
        PersonalFaena.objects
        .filter(
            personal_id__in=personas,
            activo=True,
            fecha_inicio__lte=date(year, month, days_in_month)
        )
        .select_related('faena', 'tipo_turno', 'faena__tipo_turno')
        .values('personal_id', 'faena_id', 'faena__nombre', 'fecha_inicio', 'tipo_turno__dias_trabajo', 
                'tipo_turno__dias_descanso', 'faena__tipo_turno__dias_trabajo', 
                'faena__tipo_turno__dias_descanso')
    )
    
    # Crear mapa de días en faena y días de descanso para cada persona
    dias_en_faena = {}
    dias_de_descanso = {}
    
    print(f"DEBUG: asignaciones_faena encontradas: {len(asignaciones_faena)}")
    for a in asignaciones_faena:
        print(f"DEBUG: Asignación - Personal: {a['personal_id']}, Faena: {a['faena__nombre']}, Fecha inicio: {a['fecha_inicio']}")
    
    for a in asignaciones_faena:
        personal_id_str = str(a['personal_id'])
        if personal_id_str not in dias_en_faena:
            dias_en_faena[personal_id_str] = set()
        
        # Calcular la fecha fin basándose en el turno
        from datetime import timedelta
        fecha_inicio = a['fecha_inicio']
        
        # Obtener el turno específico de la persona o usar el de la faena
        dias_trabajo = a['tipo_turno__dias_trabajo'] or a['faena__tipo_turno__dias_trabajo']
        dias_descanso = a['tipo_turno__dias_descanso'] or a['faena__tipo_turno__dias_descanso']
        
        if dias_trabajo and dias_descanso:
            print(f"DEBUG: Personal {personal_id_str} tiene turno {dias_trabajo}x{dias_descanso}")
            # Calcular el ciclo completo del turno
            duracion_ciclo = dias_trabajo + dias_descanso
            
            # Para cada día del mes, determinar si está en trabajo o descanso
            for d in range(1, days_in_month + 1):
                fecha_actual = date(year, month, d)
                dias_desde_inicio_actual = (fecha_actual - fecha_inicio).days
                
                if dias_desde_inicio_actual >= 0:  # Solo días futuros al inicio de la asignación
                    dia_en_ciclo_actual = dias_desde_inicio_actual % duracion_ciclo
                    
                    if dia_en_ciclo_actual < dias_trabajo:
                        # Está en días de trabajo
                        dias_en_faena[personal_id_str].add(d)
                    else:
                        # Está en días de descanso
                        if personal_id_str not in dias_de_descanso:
                            dias_de_descanso[personal_id_str] = set()
                        dias_de_descanso[personal_id_str].add(d)
            
            print(f"DEBUG: Personal {personal_id_str} - Días en faena: {sorted(dias_en_faena[personal_id_str])}")
            print(f"DEBUG: Personal {personal_id_str} - Días de descanso: {sorted(dias_de_descanso.get(personal_id_str, set()))}")
        else:
            print(f"DEBUG: Personal {personal_id_str} NO tiene turno definido")
            # Si no hay turno definido, asumir que está en faena todos los días
            fecha_fin = min(date(year, month, days_in_month), fecha_inicio + timedelta(days=30))
            for d in iter_days(fecha_inicio, fecha_fin):
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
                        fecha_fin = min(date(year, month, days_in_month), fecha_inicio + timedelta(days=30))
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            faena_nombre = a['faena__nombre']
                            break
                
                # Buscar información detallada de la faena para este día
                faena_info = None
                for a in asignaciones_faena:
                    if str(a['personal_id']) == pid:
                        fecha_inicio = a['fecha_inicio']
                        # Calcular fecha fin basándose en el turno o usar un límite razonable
                        if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso']:
                            # Si hay turno, calcular fecha fin basándose en el turno
                            dias_ciclo = a['tipo_turno__dias_trabajo'] + a['tipo_turno__dias_descanso']
                            fecha_fin = fecha_inicio + timedelta(days=dias_ciclo * 3)  # 3 ciclos como máximo
                        else:
                            # Si no hay turno, usar un límite de 30 días
                            fecha_fin = fecha_inicio + timedelta(days=30)
                        
                        fecha_fin = min(date(year, month, days_in_month), fecha_fin)
                        
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            # Formatear fecha en español
                            fecha_inicio_str = a['fecha_inicio'].strftime('%d de %B de %Y') if a['fecha_inicio'] else 'No especificada'
                            faena_info = {
                                'faena_id': a['faena_id'],
                                'faena_nombre': a['faena__nombre'],
                                'fecha_inicio': fecha_inicio_str,
                                'turno': f"{a['tipo_turno__dias_trabajo']}x{a['tipo_turno__dias_descanso']}" if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso'] else "Sin turno específico"
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
                        if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso']:
                            # Si hay turno, calcular fecha fin basándose en el turno
                            dias_ciclo = a['tipo_turno__dias_trabajo'] + a['tipo_turno__dias_descanso']
                            fecha_fin = fecha_inicio + timedelta(days=dias_ciclo * 3)  # 3 ciclos como máximo
                        else:
                            # Si no hay turno, usar un límite de 30 días
                            fecha_fin = fecha_inicio + timedelta(days=30)
                        
                        fecha_fin = min(date(year, month, days_in_month), fecha_fin)
                        
                        if fecha_inicio <= date(year, month, day_num) <= fecha_fin:
                            # Formatear fecha en español
                            fecha_inicio_str = a['fecha_inicio'].strftime('%d de %B de %Y') if a['fecha_inicio'] else 'No especificada'
                            faena_info = {
                                'faena_id': a['faena_id'],
                                'faena_nombre': a['faena__nombre'],
                                'fecha_inicio': fecha_inicio_str,
                                'turno': f"{a['tipo_turno__dias_trabajo']}x{a['tipo_turno__dias_descanso']}" if a['tipo_turno__dias_trabajo'] and a['tipo_turno__dias_descanso'] else "Sin turno específico"
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

    # ORDENAR ESTADOS POR PRIORIDAD ANTES DE ENVIAR AL FRONTEND
    # Prioridad 1: Estados base (disponible, en faena, descanso) - Se muestran ARRIBA
    # Prioridad 2: Estados secundarios (turno, vacaciones, permiso) - Se muestran ABAJO
    # Prioridad 3: Estados de alta prioridad (licencia médica) - Se muestran AL FINAL
    # 
    # IMPORTANTE: El estado "disponible" se remueve automáticamente cuando hay otros estados
    # porque no puede coexistir con licencia, descanso, permiso, vacaciones, etc.
    
    for pid, days in results.items():
        for d, estados in days.items():
            # Ordenar estados por prioridad (menor número = mayor prioridad visual)
            estados.sort(key=lambda x: x['prioridad'])
            
            # Debug: mostrar el orden final de estados para cada día
            if estados:
                print(f"DEBUG: Persona {pid}, Día {d} - Estados ordenados: {[estado['tipo'] for estado in estados]}")

    # Debug: imprimir el resultado
    print(f"DEBUG: resultados para {len(results)} personas")
    for pid, days in results.items():
        print(f"  Persona {pid}: {len([d for d in days.values() if d])} días con estados")
        # Mostrar algunos ejemplos de estados
        for day, estados in list(days.items())[:3]:  # Solo primeros 3 días
            if estados:
                print(f"    Día {day}: {estados}")

    return JsonResponse({'results': results})


@require_GET
def get_turnos(request):
    """Obtener lista de turnos disponibles"""
    try:
        print(f"DEBUG: get_turnos - Iniciando...")
        turnos = TipoTurno.objects.filter(activo=True).values('tipo_turno_id', 'nombre').order_by('nombre')
        print(f"DEBUG: get_turnos - Query ejecutada, {turnos.count()} turnos encontrados")
        
        turnos_list = list(turnos)
        print(f"DEBUG: get_turnos - Turnos convertidos a lista: {turnos_list}")
        
        response_data = {'results': turnos_list}
        print(f"DEBUG: get_turnos - Respuesta final: {response_data}")
        
        return JsonResponse(response_data)
    except Exception as e:
        print(f"ERROR en get_turnos: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        return JsonResponse({'error': str(e)}, status=500)


@require_GET
def get_faena_turno(request, faena_id):
    """Obtener el turno y fechas de una faena específica"""
    try:
        faena = Faena.objects.get(faena_id=faena_id)
        
        # Información del turno
        turno_info = faena.tipo_turno.nombre if faena.tipo_turno else 'No especificado'
        
        # Información de fechas
        fecha_inicio = faena.fecha_inicio.strftime('%d/%m/%Y') if faena.fecha_inicio else 'No especificada'
        fecha_fin = faena.fecha_fin.strftime('%d/%m/%Y') if faena.fecha_fin else 'No especificada'
        
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


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


@csrf_exempt
@require_POST
def assign_personal_to_faena(request):
    """Asignar personal a una faena"""
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
                            'fecha_inicio': fecha_inicio
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
            
            if asignaciones_existentes.exists():
                print(f"DEBUG: Desactivando asignaciones existentes...")
                asignaciones_existentes.update(activo=False)
                print(f"DEBUG: Asignaciones desactivadas exitosamente")
            
            # Crear nueva asignación
            print(f"DEBUG: Creando nueva asignación...")
            nueva_asignacion = PersonalFaena.objects.create(
                personal_id=personal_id,
                faena_id=faena_id,
                tipo_turno_id=turno_id,
                fecha_inicio=fecha_inicio,
                activo=True
            )
            
            print(f"DEBUG: Nueva asignación creada exitosamente con ID: {nueva_asignacion.personal_faena_id}")
            
            # Crear log de auditoría
            try:
                # Obtener información del personal y faena para el log
                personal = Personal.objects.get(personal_id=personal_id)
                faena = Faena.objects.get(faena_id=faena_id)
                turno_info = f" (Turno: {nueva_asignacion.tipo_turno.nombre})" if nueva_asignacion.tipo_turno else ""
                
                descripcion = f"Se asignó a {personal.nombre} {personal.apepat} a la faena '{faena.nombre}' desde {fecha_inicio}{turno_info}"
                
                AuditLog.crear_log(
                    accion='asignar',
                    tabla_afectada='PersonalFaena',
                    registro_id=nueva_asignacion.personal_faena_id,
                    descripcion=descripcion,
                    usuario=get_current_user_name(request),
                    datos_nuevos={
                        'personal_id': personal_id,
                        'personal_nombre': f"{personal.nombre} {personal.apepat}",
                        'faena_id': faena_id,
                        'faena_nombre': faena.nombre,
                        'fecha_inicio': fecha_inicio,
                        'turno_id': turno_id
                    },
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
    """Remover personal de una faena específica o todas las faenas"""
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
    """Obtener logs de auditoría para mostrar en el panel lateral"""
    try:
        # Obtener parámetros de filtrado
        limit = int(request.GET.get('limit', 50))  # Límite de logs a mostrar
        accion = request.GET.get('accion', '')  # Filtrar por tipo de acción
        tabla = request.GET.get('tabla', '')  # Filtrar por tabla afectada
        usuario = request.GET.get('usuario', '')  # Filtrar por usuario
        
        # Construir query base
        logs = AuditLog.objects.all()
        
        # Aplicar filtros si se especifican
        if accion:
            logs = logs.filter(accion__icontains=accion)
        if tabla:
            logs = logs.filter(tabla_afectada__icontains=tabla)
        if usuario:
            logs = logs.filter(usuario__icontains=usuario)
        
        # Limitar resultados y ordenar por fecha más reciente
        logs = logs[:limit]
        
        # Preparar datos para el frontend
        logs_data = []
        for log in logs:
            # Obtener información adicional del cargo si es una asignación de personal
            cargo_info = 'N/A'
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
                                
                except Exception as e:
                    print(f"Error obteniendo cargo para log {log.log_id}: {str(e)}")
                    cargo_info = 'Cargo no disponible'
            
            logs_data.append({
                'id': log.log_id,
                'usuario': log.usuario or 'Usuario Calendario',
                'accion': log.accion,
                'cargo': cargo_info,
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
