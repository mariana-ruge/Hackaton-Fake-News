# ADR-0003: Foco en fake news financieras

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Cristian Hernández, Mariana Ruge
- **Tags:** producto, alcance

## Contexto

El plan original (`PLAN.md v1`) cubría fake news **en general** (salud, política, economía, LatAm, bilingüe). Cuando Mariana empezó la implementación reactiva en `main.py`, redactó un `prompt_principal` enfocado **solo en desinformación financiera**: alarmismo económico, esquemas Ponzi, "pseudo-traders", promesas de inversión sospechosas, FOMO.

Esto creaba una disonancia: el README hablaba de fake news genéricas pero el agente solo respondía a noticias financieras. Necesitábamos **alinear el alcance** antes de seguir, porque condiciona:

- El prompt del agente.
- El dataset semilla de Phoenix (futuro bonus).
- Los fact-checkers que indexamos (CNMV, SEC, Bloomberg, vs Snopes/Maldita generalistas).
- La narrativa de la demo.

## Decisión

Restringimos Blacklight Expose al dominio **fake news financieras**, con tres sub-áreas:

1. **Desinformación económica / mercado** (titulares alarmistas, rumores de bolsa).
2. **Prevención de fraudes de inversión** (Ponzi, pirámides, pseudo-traders).
3. **Análisis de promesas de inversión** en redes sociales.

Se mantiene la **nota de neutralidad geopolítica** porque las noticias financieras a menudo involucran gobiernos.

## Consecuencias

### ✅ Positivas
- **Diferenciador claro**: pocos fact-checkers cubren bien la desinformación financiera en español → nicho real.
- Permite curar `factcheckers.json` con dominios especializados (CNMV, SEC, FT, Bloomberg, Expansión).
- Demo más vendible: un caso Ponzi típico es visualmente más impactante que "¿este meme es cierto?".
- Alineado con lo que Mariana ya construyó → cero retrabajo.

### ⚠️ Negativas
- Reducimos el público potencial (no sirve para fake news sanitarias o políticas).
- Requiere prompt especializado y datasets curados al dominio.

### 🔁 Trade-offs
- Renunciamos a ser una herramienta universal a cambio de ser **buena en un dominio concreto**.

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **Volver al alcance general** | Implicaba reescribir `prompt_principal`, perdíamos el foco vendible y la coherencia con `factcheckers.json` curado. |
| **Híbrido (financiero por defecto, otros bajo flag)** | Complejidad innecesaria para una demo. Si el proyecto sobrevive al reto, ampliar es trivial. |

## Referencias

- `main.py` línea ~150 — variable `prompt_principal` con el dominio financiero.
- `scripts/seed_factcheckers.py` — incluye reguladores (CNMV, SEC) y medios financieros.
- `README.md` — sección "📰 El problema" alineada al dominio.
- Decisión confirmada en conversación 2026-06-07 (ver historial de commits posteriores a `f8aafb7`).
