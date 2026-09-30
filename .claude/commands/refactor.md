---
description: Refactoriza el archivo/módulo indicado según las convenciones de CLAUDE.md
argument-hint: <archivo o descripción de lo que refactorizar>
---

Refactorizá $ARGUMENTS siguiendo las convenciones documentadas en
`CLAUDE.md` de este repo: identificadores/docstrings en español,
responsabilidad única por módulo (no mezcles clima/terreno/autómata),
imports pesados diferidos donde aplique, y comentarios que expliquen el
porqué (no el qué).

Si el refactor toca `modelo_rothermel.py` o cualquier constante física ya
verificada contra una fuente publicada, no cambies el valor ni la fórmula sin
antes decirme qué fuente respalda el nuevo valor y esperar mi confirmación.

Después de refactorizar, corré las pruebas del proyecto:
`python -B -m unittest discover -s tests -t . -v`.
