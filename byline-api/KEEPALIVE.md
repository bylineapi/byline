# Sistema Keep-Alive para Render

## 🎯 Objetivo

Mantener la API activa en Render Free Tier, que se duerme después de 15 minutos de inactividad.

## 📋 Solución Implementada

### 1. **Keep-Alive Interno (Automático)**

- **Archivo**: `keep_alive.py`
- **Funcionamiento**: Hace ping automático cada **12 minutos** al endpoint `/health`
- **Configuración**: Se inicia automáticamente con la aplicación
- **Logs**: Registra cada ping exitoso/fallido

### 2. **Endpoint Público `/ping`**

- **URL**: `https://byline-dgpt.onrender.com/ping`
- **Respuesta**:
  ```json
  {
    "status": "ok",
    "message": "pong",
    "timestamp": "2026-05-13T00:48:00.000Z"
  }
  ```
- **Acceso**: Público (no requiere autenticación)

### 3. **Monitor Externo (Opcional - Respaldo)**

- **Archivo**: `monitor_external.py`
- **Uso**: Para servicios externos como UptimeRobot o Cron-job.org

## 🚀 Configuración

### En Render (Automático)

La variable `RENDER_EXTERNAL_URL` se configura automáticamente por Render. No necesitas hacer nada.

### Manual (Si es necesario)

Agrega en tu `.env`:

```env
RENDER_EXTERNAL_URL=https://byline-dgpt.onrender.com
```

## 📊 Monitoreo

### Ver logs del keep-alive

En los logs de Render verás:

```
Keep-alive iniciado: ping cada 12 minutos a https://byline-dgpt.onrender.com
✅ Ping exitoso a https://byline-dgpt.onrender.com/health - 2026-05-13 00:48:00
✅ Ping exitoso a https://byline-dgpt.onrender.com/health - 2026-05-13 01:00:00
```

### Verificar manualmente

```bash
curl https://byline-dgpt.onrender.com/ping
```

## 🔧 Configuración de Monitores Externos (Opcional)

### UptimeRobot

1. Ve a https://uptimerobot.com
2. Crea un monitor HTTP
3. URL: `https://byline-dgpt.onrender.com/ping`
4. Intervalo: **10 minutos**
5. Friendly Name: "Byline API Keep-Alive"

### Cron-job.org

1. Ve a https://cron-job.org
2. Crea un nuevo cron job
3. URL: `https://byline-dgpt.onrender.com/ping`
4. Schedule: Cada **10 minutos**
5. Save

## ⚙️ Personalización

### Cambiar intervalo de ping

Edita `keep_alive.py`:

```python
PING_INTERVAL_MINUTES = 12  # Cambia a 10, 14, etc.
```

## 📝 Notas Importantes

1. **El keep-alive interno es suficiente** para la mayoría de los casos
2. **Monitores externos son opcionales** pero recomendados como respaldo
3. **No hacer ping más de cada 5 minutos** para evitar abuso
4. **Render Free Tier**: 750 horas/mes (suficiente para 1 servicio 24/7)

## 🐛 Troubleshooting

### La API se sigue durmiendo

1. Verifica los logs en Render Dashboard
2. Busca mensajes de error del keep-alive
3. Verifica que `RENDER_EXTERNAL_URL` esté configurada
4. Prueba manualmente: `curl https://byline-dgpt.onrender.com/ping`

### Error de base de datos

El keep-alive NO verifica la conexión a BD. Usa `/health` para eso:

```bash
curl https://byline-dgpt.onrender.com/health
```

## 📚 Archivos Relacionados

- `keep_alive.py` - Lógica del keep-alive interno
- `monitor_external.py` - Script para monitores externos
- `main.py` - Endpoint `/ping` y configuración del lifespan
- `.env.example` - Variables de entorno de ejemplo
