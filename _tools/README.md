# Herramientas de mantenimiento de Folklorius

No forman parte del sitio publicado.

## diagnostico.py

Mide una ficha antes de tocarla: valida el marcado, los tres bloques JSON-LD,
las fechas (incluido el calculo de Pascua por Gauss), la metadata, la estructura
de cada bloque (nota de sensibilidad, imprescindibles, FAQ contra FAQPage,
vocabulario, etiquetas, relacionadas), la integridad de enlaces e imagenes y el
lexico prohibido.

Uso:

    python3 _tools/diagnostico.py semana-santa-leon.html

Sin argumentos mide semana-santa-orihuela.html, que es la referencia canonica y
debe dar siempre 0 avisos. Si Orihuela deja de dar 0, el que esta mal es el
script, no la ficha.
