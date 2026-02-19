# MIA - Asistente Virtual de Portabilidad Telcel (Modular)

Este proyecto es una versión modularizada de MIA, un bot de WhatsApp diseñado para gestionar leads de portabilidad a Telcel. Utiliza la API de Meta (WhatsApp Cloud API) e Inteligencia Artificial (Google Gemini) para interactuar con los clientes, calificar leads y agendar llamadas.

## 🚀 Características

- **Modular**: Código dividido por responsabilidades (Base de datos, IA, Rutas, Servicios).
- **IA Generativa**: Integración con Google Gemini para respuestas persuasivas y empáticas.
- **Seguimiento Automático**: Hilo de fondo que reactiva conversaciones inactivas según reglas de negocio.
- **Dashboard Web**: Interfaz para monitorear chats en tiempo real, enviar mensajes manuales y reactivar el bot.
- **Trazabilidad**: Integración con SQL Server para guardar logs de mensajes, estados de sesión y referidos.

## 🛠️ Estructura del Proyecto

- `app.py`: Punto de entrada del servidor Flask.
- `config.py`: Gestión de configuración y variables de entorno.
- `database.py`: Todas las operaciones con SQL Server.
- `logger.py`: Implementación de DualLogger para logs en consola y archivos.
- `routes/`:
  - `webhooks.py`: Gestión de mensajes entrantes de WhatsApp.
  - `api.py`: Endpoints para el dashboard.
  - `dashboard.py`: Renderizado de la interfaz web.
- `services/`:
  - `ai.py`: Configuración de Google Gemini.
  - `meta.py`: Cliente para la API de WhatsApp.
  - `logic.py`: Máquina de estados de la conversación.
  - `scheduler.py`: Lógica de re-vinculación automática (hilo de seguimiento).

## 📋 Requisitos

- Python 3.8+
- SQL Server con los drivers ODBC instalados.
- Token de Acceso de Facebook (WhatsApp Cloud API).
- API Key de Google Gemini.

## ⚙️ Configuración

1. Renombra el archivo `.Env` con tus credenciales.
2. Asegúrate de que las tablas de SQL (`tb_mia_flujo_ventas`, `tb_mia_logs_mensajes`, `prepago..Referidos`, y la vista `vw_resumen_numeros_mia`) existan en tu base de datos.
3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## 🏃 Ejecución

```bash
python app.py
```

El servidor correrá en `http://localhost:5000`.

---
*Desarrollado para la optimización de ventas de portabilidad.*
