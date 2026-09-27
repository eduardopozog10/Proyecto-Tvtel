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
```

Crear un archivo `.env` utilizando `.env.example` como referencia.

Aplicar las migraciones:

```powershell
uv run python manage.py migrate
```

Iniciar el servidor:

```powershell
uv run python manage.py runserver
```

El servidor estará disponible en:

```text
http://127.0.0.1:8000/
```

## Variables de entorno

Las contraseñas, tokens y claves privadas deben guardarse únicamente en `.env`.

El archivo `.env` no debe subirse a GitHub. El archivo `.env.example` contiene solamente la estructura necesaria, sin credenciales reales.

## Estado actual

- Proyecto Django creado.
- Django REST Framework instalado.
- PostgreSQL configurado.
- Migraciones iniciales aplicadas.
- Repositorio GitHub configurado.

## Próximas etapas

1. Crear el módulo de incidentes.
2. Definir los modelos de datos.
3. Crear el endpoint de prueba.
4. Integrar la extracción con IA.
5. Implementar el webhook de WhatsApp.
6. Probar el flujo completo del MVP.
7. Construir el dashboard web.
8. Agregar soporte para audio e imágenes.