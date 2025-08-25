from django.db import models
from django.utils import timezone
from datetime import datetime


class Sexo(models.Model):
    sexo_id = models.AutoField(primary_key=True)
    sexo = models.CharField(max_length=20)

    class Meta:
        db_table = 'Sexo'

    def __str__(self) -> str:
        return self.sexo


class EstadoCivil(models.Model):
    estcivil_id = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=30)

    class Meta:
        db_table = 'EstadoCivil'

    def __str__(self) -> str:
        return self.estado


class Region(models.Model):
    region_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'Region'

    def __str__(self) -> str:
        return self.nombre


class Comuna(models.Model):
    comuna_id = models.AutoField(primary_key=True)
    region_id = models.ForeignKey(Region, on_delete=models.CASCADE, db_column='region_id')
    nombre = models.CharField(max_length=100)

    class Meta:
        db_table = 'Comuna'

    def __str__(self) -> str:
        return self.nombre


class Empresa(models.Model):
    empresa_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150)

    class Meta:
        db_table = 'Empresa'

    def __str__(self) -> str:
        return self.nombre


def obtener_ruta_documento(instance, filename):
    rut = getattr(instance, 'rut', None) or getattr(getattr(instance, 'personal_id', None), 'rut', 'misc')
    carpeta = 'Documentacion_Personal' if hasattr(instance, 'rut') else 'Licencias_Medicas'
    return f"{carpeta}/{rut}/{filename}"


class Personal(models.Model):
    personal_id = models.AutoField(primary_key=True, null=False, blank=False)
    sexo_id = models.ForeignKey(Sexo, on_delete=models.CASCADE, db_column='sexo_id', null=True, blank=True)
    estcivil_id = models.ForeignKey(EstadoCivil, on_delete=models.CASCADE, db_column='estcivil_id', null=True, blank=True)
    region_id = models.ForeignKey(Region, on_delete=models.CASCADE, db_column='region_id', null=True, blank=True)
    comuna_id = models.ForeignKey(Comuna, on_delete=models.CASCADE, db_column='comuna_id', null=True, blank=True)
    rut = models.CharField(max_length=8, null=False, blank=False, unique=True)
    dvrut = models.CharField(max_length=1, null=False, blank=False)
    nombre = models.CharField(max_length=100, null=False, blank=False)
    apepat = models.CharField(max_length=50, null=False, blank=False)
    apemat = models.CharField(max_length=50)
    fechanac = models.DateField(null=True, blank=True)
    correo = models.CharField(max_length=100, null=False, blank=False, unique=True)
    direccion = models.CharField(max_length=150, null=True, blank=True)
    activo = models.BooleanField(default=True, verbose_name='Estado')

    curriculum = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Curriculum Vitae')
    certificado_antecedentes = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Certificado de Antecedentes')
    hoja_vida_conductor = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Hoja de Vida del Conductor')
    foto_carnet = models.ImageField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Foto tipo Carnet')
    certificado_afp = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Certificado de Afiliación AFP')
    certificado_salud = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Certificado de Afiliación de Salud')
    certificado_estudios = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Certificado de Estudios')
    certificado_residencia = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Certificado de Residencia')
    fotocopia_carnet = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Fotocopia de Carnet')
    fotocopia_finiquito = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Fotocopia de Último Finiquito')
    comprobante_banco = models.FileField(upload_to=obtener_ruta_documento, null=True, blank=True, verbose_name='Formulario de Depósito Bancario')

    class Meta:
        db_table = 'Personal'

    def __str__(self):
        return f"{self.nombre} {self.apepat} {self.apemat}"

    def save(self, *args, **kwargs):
        self.rut = self.rut.upper()
        self.dvrut = self.dvrut.upper()
        self.nombre = self.nombre.upper()
        self.apepat = self.apepat.upper()
        self.apemat = self.apemat.upper()
        self.correo = self.correo.upper()
        self.direccion = self.direccion.upper() if self.direccion else None
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
    
    @property
    def faenas_activas(self):
        """Retorna las faenas activas del personal"""
        return self.personalfaena.filter(activo=True, esta_activa=True)
    
    @property
    def faena_principal(self):
        """Retorna la faena principal (la más reciente activa)"""
        return self.faenas_activas.order_by('-fecha_inicio').first()


class DeptoEmpresa(models.Model):
    depto_id = models.AutoField(primary_key=True, blank=False, null=False)
    depto = models.CharField(max_length=50, db_column='depto', blank=False, null=False)

    def __str__(self):
        return self.depto


class Cargo(models.Model):
    cargo_id = models.AutoField(primary_key=True, blank=False, null=False)
    depto_id = models.ForeignKey(DeptoEmpresa, on_delete=models.CASCADE, db_column='depto_id', blank=False, null=False)
    cargo = models.CharField(max_length=50, db_column='cargo', blank=False, null=False)

    def __str__(self):
        return self.cargo


class InfoLaboral(models.Model):
    infolab_id = models.AutoField(primary_key=True, null=False, blank=False)
    personal_id = models.ForeignKey(Personal, on_delete=models.CASCADE, db_column='personal_id', null=False, blank=False)
    empresa_id = models.ForeignKey(Empresa, on_delete=models.CASCADE, db_column='empresa_id', null=False, blank=False)
    depto_id = models.ForeignKey(DeptoEmpresa, on_delete=models.CASCADE, db_column='depto_id', null=False, blank=False)
    cargo_id = models.ForeignKey(Cargo, on_delete=models.CASCADE, db_column='cargo_id', blank=False, null=False)
    fechacontrata = models.DateField(blank=False, null=False)


class TipoAusentismo(models.Model):
    tipoausen_id = models.AutoField(primary_key=True, null=False, blank=False)
    tipo = models.CharField(max_length=100, null=False, blank=False, db_column='tipo')

    def __str__(self):
        return self.tipo


class Ausentismo(models.Model):
    ausentismo_id = models.AutoField(primary_key=True, null=False, blank=False)
    tipoausen_id = models.ForeignKey(TipoAusentismo, on_delete=models.CASCADE, db_column='tipoausen_id', null=False, blank=False)
    personal_id = models.ForeignKey(Personal, on_delete=models.CASCADE, db_column='personal_id', null=False, blank=False)
    fechaini = models.DateField(null=False, blank=False)
    fechafin = models.DateField(null=False, blank=False)
    observacion = models.TextField(max_length=250, blank=True, null=True)

    def __str__(self):
        trabajador = f"{self.personal_id.nombre} {self.personal_id.apepat} {self.personal_id.apemat}"
        return f"{self.tipoausen_id} - {trabajador} ({self.fechaini} a {self.fechafin})"


class TipoLicenciaMedica(models.Model):
    tipoLicenciaMedica_id = models.AutoField(primary_key=True, null=False, blank=False)
    tipoLicenciaMedica = models.CharField(max_length=100, null=False, blank=False)

    def __str__(self):
        return self.tipoLicenciaMedica


class LicenciaMedicaPorPersonal(models.Model):
    licenciaMedicaPorPersonal_id = models.AutoField(primary_key=True, null=False, blank=False)
    personal_id = models.ForeignKey(Personal, on_delete=models.CASCADE, db_column='personal_id', null=False, blank=False)
    tipoLicenciaMedica_id = models.ForeignKey(TipoLicenciaMedica, on_delete=models.CASCADE, db_column='tipoLicenciaMedica_id', null=False, blank=False)
    numero_folio = models.CharField(max_length=50, null=True, blank=True, verbose_name='N° Folio', default='0')
    fechaEmision = models.DateField(null=False, blank=False)
    dias_licencia = models.IntegerField(null=False, blank=False)
    fecha_fin_licencia = models.DateField(null=False, blank=False, editable=False, default=timezone.now)
    rutaDoc = models.FileField(upload_to=obtener_ruta_documento, null=False, blank=False)
    observacion = models.TextField(max_length=250, null=True, blank=True)

    def save(self, *args, **kwargs):
        from datetime import timedelta
        if self.fechaEmision and self.dias_licencia:
            self.fecha_fin_licencia = self.fechaEmision + timedelta(days=self.dias_licencia - 1)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Licencia Médica de {self.personal_id} - {self.tipoLicenciaMedica_id}"

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)


class TipoTurno(models.Model):
    """Modelo para definir tipos de turnos (ej: 7x7, 14x7, etc.)"""
    tipo_turno_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True, help_text="Ej: 7x7, 14x7, 21x7")
    dias_trabajo = models.PositiveIntegerField(help_text="Días de trabajo consecutivos")
    dias_descanso = models.PositiveIntegerField(help_text="Días de descanso consecutivos")
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'TipoTurno'
        verbose_name = 'Tipo de Turno'
        verbose_name_plural = 'Tipos de Turno'

    def __str__(self):
        return f"{self.nombre} ({self.dias_trabajo}x{self.dias_descanso})"

    @property
    def duracion_ciclo(self):
        """Retorna la duración total del ciclo en días"""
        return self.dias_trabajo + self.dias_descanso


class Faena(models.Model):
    """Modelo para definir faenas/sitios de trabajo"""
    faena_id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150, unique=True, default='SIN ASIGNAR')
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.PROTECT, null=True, blank=True)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    
    # Fechas de la faena
    fecha_inicio = models.DateField(help_text="Fecha de inicio de la faena", default=timezone.now)
    fecha_fin = models.DateField(help_text="Fecha de finalización de la faena", default=timezone.now)
    
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'Faena'
        verbose_name = 'Faena'
        verbose_name_plural = 'Faenas'

    def __str__(self):
        return self.nombre
    
    def clean(self):
        """Validar que fecha_fin sea posterior a fecha_inicio"""
        from django.core.exceptions import ValidationError
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin <= self.fecha_inicio:
            raise ValidationError('La fecha de fin debe ser posterior a la fecha de inicio.')
    
    @property
    def duracion_dias(self):
        """Retorna la duración de la faena en días"""
        if self.fecha_inicio and self.fecha_fin:
            from datetime import timedelta
            return (self.fecha_fin - self.fecha_inicio).days + 1
        return 0
    
    @property
    def esta_activa(self):
        """Retorna True si la faena está activa en la fecha actual"""
        from datetime import date
        today = date.today()
        if self.fecha_inicio and self.fecha_fin:
            return self.fecha_inicio <= today <= self.fecha_fin
        return False
    
    @property
    def personal_asignado(self):
        """Retorna el personal activamente asignado a esta faena"""
        return self.personalfaena.filter(activo=True, esta_activa=True)
    
    @property
    def cantidad_personal(self):
        """Retorna la cantidad de personal activamente asignado"""
        return self.personal_asignado.count()


class PersonalFaena(models.Model):
    """Modelo intermedio para relación muchos a muchos entre Personal y Faena"""
    personal_faena_id = models.AutoField(primary_key=True)
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, db_column='personal_id')
    faena = models.ForeignKey(Faena, on_delete=models.CASCADE, db_column='faena_id')
    
    # Fechas de asignación
    fecha_asignacion = models.DateField(auto_now_add=True, help_text="Fecha cuando se asignó la faena")
    fecha_inicio = models.DateField(help_text="Fecha de inicio en esta faena")
    
    # Turno específico para esta persona en esta faena
    tipo_turno = models.ForeignKey(TipoTurno, on_delete=models.PROTECT, null=True, blank=True, 
                                  help_text="Turno específico para esta persona (opcional, usa el de la faena si no se especifica)")
    
    # Estado de la asignación
    activo = models.BooleanField(default=True, help_text="Indica si la asignación está activa")
    
    # Información adicional
    observaciones = models.TextField(blank=True, null=True, help_text="Observaciones sobre la asignación")
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'PersonalFaena'
        verbose_name = 'Asignación de Personal a Faena'
        verbose_name_plural = 'Asignaciones de Personal a Faena'
        unique_together = ['personal', 'faena', 'fecha_inicio']

    def __str__(self):
        turno_info = f" - {self.tipo_turno.nombre}" if self.tipo_turno else ""
        return f"{self.personal} - {self.faena}{turno_info} (desde {self.fecha_inicio})"
    
    def clean(self):
        """Validar fechas de asignación"""
        from django.core.exceptions import ValidationError
        
        # Verificar que la fecha de inicio esté dentro del rango de la faena
        if self.faena and self.fecha_inicio:
            if self.fecha_inicio < self.faena.fecha_inicio:
                raise ValidationError(f'La fecha de inicio no puede ser anterior al inicio de la faena ({self.faena.fecha_inicio})')
            if self.faena.fecha_fin and self.fecha_inicio > self.faena.fecha_fin:
                raise ValidationError(f'La fecha de inicio no puede ser posterior al fin de la faena ({self.faena.fecha_fin})')
    
    @property
    def turno_efectivo(self):
        """Retorna el turno que se debe usar (el específico o el de la faena)"""
        return self.tipo_turno or self.faena.tipo_turno
    
    @property
    def fecha_fin_calculada(self):
        """Calcula la fecha de fin basándose en el turno y la duración de la faena"""
        if not self.fecha_inicio or not self.turno_efectivo:
            return None
        
        from datetime import date, timedelta
        
        # Si la faena tiene fecha fin, usar esa como límite
        fecha_limite = self.faena.fecha_fin if self.faena.fecha_fin else None
        
        # Calcular cuántos ciclos completos puede hacer la persona
        if fecha_limite:
            dias_disponibles = (fecha_limite - self.fecha_inicio).days + 1
            ciclos_completos = dias_disponibles // self.turno_efectivo.duracion_ciclo
            dias_trabajo_total = ciclos_completos * self.turno_efectivo.dias_trabajo
            
            # La fecha fin será inicio + días de trabajo
            fecha_fin = self.fecha_inicio + timedelta(days=dias_trabajo_total - 1)
            
            # Asegurar que no pase la fecha límite de la faena
            if fecha_fin > fecha_limite:
                fecha_fin = fecha_limite
            
            return fecha_fin
        
        return None
    
    @property
    def esta_activa(self):
        """Retorna True si la asignación está activa en la fecha actual"""
        from datetime import date
        today = date.today()
        if not self.activo:
            return False
        if self.fecha_inicio <= today:
            fecha_fin = self.fecha_fin_calculada
            if fecha_fin is None or today <= fecha_fin:
                return True
        return False
    
    @property
    def duracion_dias(self):
        """Retorna la duración de la asignación en días"""
        if self.fecha_inicio:
            fecha_fin = self.fecha_fin_calculada
            if fecha_fin:
                from datetime import timedelta
                return (fecha_fin - self.fecha_inicio).days + 1
            else:
                # Si no hay fecha fin calculada, contar desde inicio hasta hoy
                from datetime import date
                today = date.today()
                if today >= self.fecha_inicio:
                    return (today - self.fecha_inicio).days + 1
        return 0
    
    @property
    def proximo_cambio_turno(self):
        """Retorna la fecha del próximo cambio de turno"""
        if not self.fecha_inicio or not self.turno_efectivo:
            return None
        
        from datetime import date, timedelta
        today = date.today()
        
        if today < self.fecha_inicio:
            return self.fecha_inicio
        
        # Calcular cuántos días han pasado desde el inicio
        dias_transcurridos = (today - self.fecha_inicio).days
        
        # Calcular en qué parte del ciclo estamos
        ciclo_actual = dias_transcurridos // self.turno_efectivo.duracion_ciclo
        dia_en_ciclo = dias_transcurridos % self.turno_efectivo.duracion_ciclo
        
        if dia_en_ciclo < self.turno_efectivo.dias_trabajo:
            # Estamos en días de trabajo, próximo cambio es al fin del trabajo
            proximo_cambio = self.fecha_inicio + timedelta(days=(ciclo_actual * self.turno_efectivo.duracion_ciclo) + self.turno_efectivo.dias_trabajo)
        else:
            # Estamos en días de descanso, próximo cambio es al fin del descanso
            proximo_cambio = self.fecha_inicio + timedelta(days=(ciclo_actual + 1) * self.turno_efectivo.duracion_ciclo)
        
        return proximo_cambio


# Agregar campo faena_id a InfoLaboral después de que Faena esté definido
InfoLaboral.add_to_class('faena_id', models.ForeignKey(Faena, on_delete=models.CASCADE, db_column='faena_id', null=True, blank=True))


class AuditLog(models.Model):
    """Modelo para registrar todos los cambios en el sistema de planificación"""
    log_id = models.AutoField(primary_key=True)
    usuario = models.CharField(max_length=100, null=True, blank=True)  # Nombre del usuario que hizo el cambio
    accion = models.CharField(max_length=50)  # 'asignar', 'remover', 'editar', 'crear', 'eliminar'
    tabla_afectada = models.CharField(max_length=50)  # 'PersonalFaena', 'Ausentismo', 'LicenciaMedica'
    registro_id = models.IntegerField()  # ID del registro afectado
    datos_anteriores = models.JSONField(null=True, blank=True)  # Estado anterior del registro
    datos_nuevos = models.JSONField(null=True, blank=True)  # Nuevo estado del registro
    fecha_hora = models.DateTimeField(auto_now_add=True)  # Cuándo ocurrió el cambio
    ip_address = models.GenericIPAddressField(null=True, blank=True)  # IP desde donde se hizo el cambio
    descripcion = models.TextField()  # Descripción detallada del cambio
    detalles_adicionales = models.JSONField(null=True, blank=True)  # Información adicional como contexto

    class Meta:
        db_table = 'AuditLog'
        ordering = ['-fecha_hora']  # Más recientes primero
        verbose_name = 'Log de Auditoría'
        verbose_name_plural = 'Logs de Auditoría'

    def __str__(self):
        return f"{self.accion} en {self.tabla_afectada} - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

    @classmethod
    def crear_log(cls, accion, tabla_afectada, registro_id, descripcion, 
                  usuario=None, datos_anteriores=None, datos_nuevos=None, 
                  ip_address=None, detalles_adicionales=None):
        """Método de clase para crear logs de manera consistente"""
        return cls.objects.create(
            usuario=usuario,
            accion=accion,
            tabla_afectada=tabla_afectada,
            registro_id=registro_id,
            datos_anteriores=datos_anteriores,
            datos_nuevos=datos_nuevos,
            ip_address=ip_address,
            descripcion=descripcion,
            detalles_adicionales=detalles_adicionales
        )
