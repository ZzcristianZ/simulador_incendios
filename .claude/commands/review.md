---
description: Revisa los cambios sin confirmar del repo (diff) en busca de errores y credenciales hardcodeadas
---

Revisa el estado actual del working tree de este repositorio Python/Streamlit.

1. Corre `git status` y `git diff` (staged y sin stage) para ver exactamente
   qué cambió.
2. Lee cada archivo modificado completo (no solo el diff) cuando el cambio
   toque `modelo_rothermel.py`, `simulador_automata.py` o cualquier constante
   física — ahí un error de signo o de unidad no se nota en un diff de 3
   líneas.
3. Señala:
   - Errores de lógica o de tipos.
   - Credenciales, tokens o llaves de API hardcodeadas (este proyecto NO
     debería tener ninguna: todas las APIs que usa — Nominatim, Overpass,
     Open-Meteo — son públicas y sin autenticación; cualquier string que
     parezca una llave es sospechoso).
   - Violaciones de las convenciones de `CLAUDE.md` (imports pesados fuera
     de `if ejecutar:`, constantes físicas sin cita de fuente, mezcla de
     idioma en identificadores, etc.).
   - Cambios a `modelo_rothermel.py` que alteren constantes o fórmulas ya
     verificadas sin justificar la fuente del nuevo valor.
4. Reporta los hallazgos organizados por archivo, con la línea exacta.

No apliques ningún cambio ni corrijas nada — esto es solo un reporte. Si
querés que aplique una corrección puntual, decímelo después de ver el reporte.
