---
description: Checklist de 20 puntos de seguridad pre-producción para este proyecto (solo reporta, no corrige)
---

Recorré este proyecto (Python/Streamlit, sin backend ni base de datos propia,
solo consumidor de tres APIs públicas sin autenticación: Nominatim, Overpass
y Open-Meteo) contra este checklist de 20 puntos. Para cada uno reportá
**✅ / ⚠️ / ❌** más una línea de evidencia (archivo:línea cuando aplique).
Donde el punto no aplique a este stack, marcá **N/A** y decí por qué en una
línea — no lo omitas en silencio.

1. **Secret scanning** — buscá strings que parezcan API keys, tokens o
   contraseñas hardcodeadas en el código (`grep -rniE` por patrones típicos).
2. **`.env` en `.gitignore`** — este repo no tiene `.env` ni `.gitignore`;
   confirmá que sigue siendo así y que no se agregó ningún secreto a un
   archivo de config versionado.
3. **Historial de git** — revisá `git log` en busca de commits que hayan
   agregado y luego "eliminado" un secreto (sigue en el historial).
4. **Validación de entradas** — la dirección/coordenadas que ingresa el
   usuario en `app.py` (lat/lon manuales, texto libre de dirección) ¿se
   validan antes de usarse en llamadas HTTP?
5. **XSS** — `app.py` inyecta HTML crudo del mapa Folium vía
   `components.html(m._repr_html_(), ...)`; confirmá que ese HTML no incorpora
   texto sin sanitizar que venga de una fuente no confiable.
6. **Autenticación/sesiones/tokens** — N/A esperable (no hay login); confirmá
   que sigue sin haber ninguno.
7. **Control de acceso** — N/A esperable (herramienta de un solo usuario/
   sesión local); confirmá que sigue siendo así.
8. **CORS** — N/A esperable (no expone una API HTTP propia); confirmá.
9. **Rate limiting hacia terceros** — Overpass/Nominatim tienen políticas de
   uso; confirmá que siguen existiendo los timeouts y el failover de espejos
   en `ingesta_geografica.py`.
10. **CSRF** — N/A esperable (Streamlit, sin endpoints de mutación propios);
    confirmá.
11. **Cabeceras HTTP** — revisá si hace falta algo más allá de lo que
    Streamlit maneja por defecto para el modo de despliegue actual.
12. **Manejo de errores/debug en producción** — los bloques `except` de
    `app.py` (`ValueError`, `KeyError`, `Exception`) ¿exponen trazas internas
    o rutas del sistema al usuario final?
13. **Carga de archivos** — N/A esperable (no hay feature de subida de
    archivos); confirmá.
14. **Cifrado y hashing** — N/A esperable (no se almacenan contraseñas ni
    datos sensibles); confirmá.
15. **Auditoría de dependencias** — corré `pip list --outdated` contra
    `requirements.txt`; si `pip-audit` no está instalado, decilo explícitamente
    en vez de omitir el punto.
16. **Verificación de webhooks y APIs de terceros** — Nominatim/Overpass/
    Open-Meteo: ¿se usa User-Agent apropiado, timeout, y validación de la
    forma de la respuesta antes de confiar en ella (ver `ingesta_geografica.py`)?
17. **Cierre de sesión** — N/A esperable (no hay sesiones de usuario);
    confirmá.
18. **Logs sin PII** — confirmá que la dirección/coordenadas que ingresa el
    usuario no se escriben a ningún log persistente.
19. **Minificación/sourcemaps expuestos** — N/A esperable (no hay build
    frontend propio, Streamlit sirve su propio bundle); confirmá.
20. **Pruebas de seguridad automatizadas** — hoy no existen; decilo
    explícitamente como ❌ en vez de inventar que sí hay.

No corrijas nada todavía. Terminá con un resumen de cuántos ✅/⚠️/❌/N/A y
dejame elegir cuáles atacar primero.
