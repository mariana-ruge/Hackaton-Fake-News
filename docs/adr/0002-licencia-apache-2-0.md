# ADR-0002: Licencia Apache 2.0

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Cristian Hernández
- **Tags:** legal

## Contexto

El reto exige que el repositorio sea **público y con una licencia OSS detectable**, visible en la sección *About* del repo. Hay que elegir antes de hacer el repo público.

Las dos opciones razonables para un proyecto OSS son **MIT** y **Apache 2.0**. Para un agente que integra varios MCPs de partners empresariales (Elastic, Bright Data, Arize), el tema de **patentes** importa más que en un proyecto puramente hobby.

## Decisión

Distribuimos Blacklight Expose bajo **Apache License 2.0**.

## Consecuencias

### ✅ Positivas
- **Cláusula explícita de patentes** (Sección 3): cada contribuyente concede licencia de patentes; si alguien demanda, pierde su licencia. Protege a usuarios y mantenedores.
- Preferida por Google y empresas grandes → buena señal para los jueces del reto (organizado por Google).
- GitHub detecta automáticamente `LICENSE` con su texto canónico y muestra `Apache-2.0` en el *About*.
- Permite uso comercial, modificación y distribución sin restricciones más allá de mantener el aviso y los cambios marcados.

### ⚠️ Negativas
- Texto largo (~200 líneas) vs los ~20 de MIT.
- Requiere mantener un archivo `NOTICE` si se añade.

### 🔁 Trade-offs
- Renunciamos a la brevedad de MIT a cambio de protección de patentes y "señal corporativa".

## Alternativas consideradas

| Opción | Por qué se descartó |
|---|---|
| **MIT** | Permisiva y ultracorta, pero **no menciona patentes**. Suficiente para hobby, débil para un proyecto que integra varios servicios de partners. |
| **GPL v3** | Demasiado restrictiva para un agente que otros podrían querer integrar en productos cerrados. |
| **Sin licencia** | Por defecto sería "todos los derechos reservados", violaría el requisito explícito del reto. |

## Referencias

- `LICENSE` — texto íntegro Apache 2.0.
- README badge: `![License: Apache 2.0]`.
- Commit `daf9d20` "Añadiendo LICENSE".
