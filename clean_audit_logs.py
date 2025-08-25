#!/usr/bin/env python
"""
Script temporal para limpiar la tabla AuditLog y resetear el auto-increment
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion.settings')
django.setup()

from core.models import AuditLog

def clean_audit_logs():
    """Limpiar todos los logs de auditoría"""
    try:
        # Contar logs antes de limpiar
        count_before = AuditLog.objects.count()
        print(f"Logs antes de limpiar: {count_before}")
        
        # Eliminar todos los logs
        AuditLog.objects.all().delete()
        
        # Verificar que se eliminaron
        count_after = AuditLog.objects.count()
        print(f"Logs después de limpiar: {count_after}")
        
        if count_after == 0:
            print("✅ Tabla AuditLog limpiada exitosamente")
            print("📝 Los nuevos logs tendrán IDs empezando desde 1")
        else:
            print("❌ Error: No se pudieron eliminar todos los logs")
            
    except Exception as e:
        print(f"❌ Error al limpiar logs: {str(e)}")

if __name__ == "__main__":
    print("🧹 Limpiando tabla AuditLog...")
    clean_audit_logs()
    print("✨ Proceso completado")
