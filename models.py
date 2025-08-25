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
    
    # Campos de documentos
    curriculum = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Curriculum Vitae'
    )
    certificado_antecedentes = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Certificado de Antecedentes'
    )
    hoja_vida_conductor = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Hoja de Vida del Conductor'
    )
    foto_carnet = models.ImageField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Foto tipo Carnet'
    )
    certificado_afp = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Certificado de Afiliación AFP'
    )
    certificado_salud = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Certificado de Afiliación de Salud'
    )
    certificado_estudios = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Certificado de Estudios'
    )
    certificado_residencia = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Certificado de Residencia'
    )
    fotocopia_carnet = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Fotocopia de Carnet'
    )
    fotocopia_finiquito = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Fotocopia de Último Finiquito'
    )
    comprobante_banco = models.FileField(
        upload_to=obtener_ruta_documento,
        storage=OverwriteStorage(),
        null=True, blank=True,
        verbose_name='Formulario de Depósito Bancario'
    )

    def __str__(self):
        return self.nombre + " " + self.apepat + " " + self.apemat
    
    class Meta:
        db_table = 'Personal'

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
        # Lista de campos de archivo
        file_fields = [
            'curriculum', 'certificado_antecedentes', 'hoja_vida_conductor',
            'foto_carnet', 'certificado_afp', 'certificado_salud',
            'certificado_estudios', 'certificado_residencia', 'fotocopia_carnet',
            'fotocopia_finiquito', 'comprobante_banco'
        ]
        
        # Eliminar cada archivo
        for field_name in file_fields:
            file = getattr(self, field_name)
            if file:
                try:
                    if os.path.isfile(file.path):
                        os.remove(file.path)
                except Exception as e:
                    print(f"Error al eliminar {field_name}: {e}")
                
        # Eliminar la carpeta del personal si está vacía
        rut_folder = os.path.join('media', 'Documentacion_Personal', self.rut)
        try:
            if os.path.exists(rut_folder) and not os.listdir(rut_folder):
                os.rmdir(rut_folder)
        except Exception as e:
            print(f"Error al eliminar carpeta: {e}")
            
        super().delete(*args, **kwargs)

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
    cargo_id = models.ForeignKey(Cargo, on_delete=models.CASCADE, db_column='cargo_id',blank=False, null=False)
    fechacontrata = models.DateField(blank=False, null=False)


class TipoAusentismo(models.Model):
    tipoausen_id = models.AutoField(primary_key=True, null=False, blank=False)
    tipo = models.CharField(max_length=100, null=False, blank=False, db_column='tipo' )

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
    fecha_fin_licencia = models.DateField(null=False, blank=False, editable=False, default=datetime.now)
    rutaDoc = models.FileField(upload_to=obtener_ruta_documento, storage=OverwriteStorage, null=False, blank=False)
    observacion = models.TextField(max_length=250, null=True, blank=True)

    def save(self, *args, **kwargs):
        from datetime import timedelta
        if self.fechaEmision and self.dias_licencia:
            self.fecha_fin_licencia = self.fechaEmision + timedelta(days=self.dias_licencia - 1)
        super().save(*args, **kwargs)



    def __str__(self):
        return f"Licencia Médica de {self.personal_id} - {self.tipoLicenciaMedica_id}"

    def delete(self, *args, **kwargs):
        # Guardar la ruta del archivo antes de eliminar el registro
        if self.rutaDoc:
            try:
                file_path = self.rutaDoc.path
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"Archivo eliminado: {file_path}")
                
                # Intentar eliminar la carpeta Licencias_Medicas si está vacía
                license_folder = os.path.dirname(file_path)
                if os.path.exists(license_folder) and not os.listdir(license_folder):
                    os.rmdir(license_folder)
                    print(f"Carpeta vacía eliminada: {license_folder}")
                    
            except Exception as e:
                print(f"Error al eliminar archivo de licencia médica: {e}")
                
        super().delete(*args, **kwargs)


