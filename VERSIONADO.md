# Guía de Manejo de Versiones - MIA Modular

Este documento establece las reglas para el trabajo colaborativo y control de versiones del proyecto MIA.

## Estrategia de Ramas (Git Flow Simplificado)

1. **`main`**: Código estable en producción. Solo se actualiza mediante merges de `develop`.
2. **`develop`**: Rama base para el desarrollo diario. Contiene las últimas integraciones terminadas.
3. **`feature/nombre-mejora`**: Ramas temporales para nuevas funcionalidades o correcciones.
   - Ejemplo: `feature/dashboard-stats`, `feature/fix-sql-connection`.

## Flujo de Trabajo Recomendado

1. Asegúrate de estar en `develop`: `git checkout develop`
2. Baja los últimos cambios: `git pull origin develop`
3. Crea tu rama de trabajo: `git checkout -b feature/mi-mejora`
4. Realiza tus cambios y haz commits descriptivos:
   ```bash
   git add .
   git commit -m "feat: añade filtro por zona en el dashboard"
   ```
5. Sube tu rama: `git push origin feature/mi-mejora`
6. Abre un **Pull Request** en GitHub hacia la rama `develop`.

## Versionado Semántico (SemVer)

Usamos el formato `vX.Y.Z`:
- **X (Major)**: Cambios estructurales masivos.
- **Y (Minor)**: Nuevas funcionalidades (ej: nuevo endpoint, nueva vista).
- **Z (Patch)**: Corrección de bugs o ajustes menores.

Para marcar una versión estable:
```bash
git tag -a v1.0.0 -m "Versión 1.0.0: Refactorización modular completa"
git push origin v1.0.0
```

## Reglas de Oro
- **NUNCA** subas el archivo `.Env` o credenciales.
- **NUNCA** trabajes directamente en `main`.
- **SIEMPRE** haz un `git pull` antes de empezar a trabajar para evitar conflictos.
- Los archivos ya no llevan versión en el nombre (ej: usar `app.py` en lugar de `app_v2.py`).
