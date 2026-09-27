# TVTEL Incidentes

Sistema para registrar y gestionar reportes técnicos enviados mediante WhatsApp.

## Objetivo del MVP

El primer MVP permitirá el siguiente flujo:

1. Un técnico envía un reporte de falla por texto mediante WhatsApp.
2. WhatsApp Cloud API entrega el mensaje al webhook de Django.
3. La IA extrae la información estructurada del incidente.
4. El backend valida si faltan datos.
5. Si faltan datos, el sistema los solicita por WhatsApp.
6. Cuando la información está completa, el incidente se almacena en PostgreSQL.
7. El técnico recibe una confirmación por WhatsApp.

## Tecnologías

- Python 3.13
- Django 5.2
- Django REST Framework
- PostgreSQL 18
- WhatsApp Cloud API
- IA para extracción estructurada
- uv para dependencias y entorno virtual

## Configuración local

Instalar las dependencias:

```powershell
uv sync