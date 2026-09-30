---
description: Instala dependencias, verifica sintaxis y reporta fallos con los comandos reales de este proyecto
---

Corré, en orden, los comandos reales de este proyecto (no genéricos — están
documentados en `CLAUDE.md`):

1. `pip install -r requirements.txt`
2. **Formateo: no aplica.** No hay formateador instalado en este proyecto
   (sin black/ruff/flake8/autopep8) — no lo inventes ni lo instales sin que
   te lo pida explícitamente.
3. Pruebas: `python -B -m unittest discover -s tests -t . -v`
4. Como smoke test funcional opcional (requiere internet, tarda por las
   llamadas a Nominatim/Overpass/Open-Meteo): `timeout 60 python main_prueba.py`
   y confirmá que llega hasta "FIN DE LA SIMULACIÓN" sin traceback.

Reportá cada paso con su resultado (éxito/fallo) y, si algo falla, el error
completo — no lo resumas ni lo omitas. No corrijas nada automáticamente:
solo reportá.
