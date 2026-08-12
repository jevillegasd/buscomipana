# Guía de Identidad Visual y UI/UX: BuscoMiPana

Este documento especifica la identidad de marca, el sistema visual y los principios de interfaz para la aplicación **BuscoMiPana**. Está estructurado para ser utilizado como prompt o especificación técnica de contexto en herramientas de IA (como Claude) o para el equipo de desarrollo.

---

## 1. Misión y Pilares de Diseño

* **Propósito:** Facilitar la localización y reporte de estado de seres queridos durante emergencias y crisis en Colombia y Latinoamérica.
* **Filosofía Visual:** **Eficiencia Extrema + Calma.** El diseño prioritario es el rendimiento técnico (modo *offline-first*, bajo consumo de datos 2G/3G y bajo consumo de batería).
* **Principios UI:**
1. **Cero distracciones:** Interfaz basada exclusivamente en texto, alto contraste y formas geométricas.
2. **Cero carga de red innecesaria:** Sin fotos de perfil pesadas, sin fuentes externas descargables, sin animaciones complejas.
3. **Comprensión instantánea:** Las acciones críticas se entienden en menos de 1 segundo bajo alto estrés.



---

## 2. Paleta de Colores — "Noche Templada" (Modo Oscuro Cálido)

La app utiliza **Modo Oscuro estricto por defecto** para preservar la batería de las personas durante un apagón o emergencia. La paleta se aleja del negro OLED neutro y de los colores semáforo saturados: usa un carbón con matiz cálido y estados suavizados, para transmitir calma y certeza en vez de alarma — sin sacrificar el contraste que exige el uso bajo estrés.

| Rol de Color | Nombre | Código HEX | Uso / Aplicación |
| --- | --- | --- | --- |
| **Fondo Principal** | Fondo Noche Templada | `#17140F` | Superficie base de toda la app (Ahorro OLED, matiz cálido). |
| **Superficie / Cards** | Gris Tarjeta Cálido | `#241F1A` | Módulos, contenedores de contactos y listas. |
| **Marca Principal** | Ocre Templado | `#CC8B3C` | Acciones neutras, enlaces, botones secundarios, cabeceras. |
| **Estado "Estoy Bien"** | Verde Salvia | `#6FB98F` | Botón principal de estado positivo, badges de "Seguro". |
| **Estado "Necesito Ayuda"** | Terracota | `#E1755F` | Botón de auxilio, alertas críticas. |
| **Estado "Esperando"** | Dorado Suave | `#E8C468` | Solicitudes pendientes de Handshake, estados dudosos. |
| **Texto Principal** | Blanco Cálido | `#F5EFE6` | Títulos, estados y nombres de personas (Alto contraste). |
| **Texto Secundario** | Taupe Atenuado | `#B8A99A` | Metadatos, horas de actualización, instrucciones. |

Nota de contraste: los botones sólidos (`bg-safe`, `bg-danger`, `bg-brand`) usan texto oscuro (`#17140F`) en vez de blanco — los tonos salvia/terracota/ocre son más claros que los rojo/verde/azul saturados originales, así que el texto oscuro es el que cumple contraste AA, no el claro.

---

## 3. Sistema Tipográfico

Para garantizar que la aplicación ocupe el menor espacio posible y cargue instantáneamente en redes inestables, **no se utilizan fuentes descargadas (Google Fonts o similares)**. Se usa exclusivamente la pila tipográfica del sistema del dispositivo (*System Font Stack*).

```css
/* Stack tipográfico oficial */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;

```

### Jerarquía Tipográfica

* **Títulos de pantalla / Alertas:** Bold (700) | 24px
* **Nombres / Estados principales:** SemiBold (600) | 18px
* **Cuerpo de texto / Instrucciones:** Regular (400) | 14px - 16px
* **Metadatos (Hora, Teléfono, Proxy):** Regular (400) | 12px

---

## 4. Iconografía e Ilustraciones

* **Formato único:** Íconos vectoriales SVG limpios e inyectados directamente en el código (Inline SVG). Tamaño máximo por ícono: **1 KB**.
* **Estilo:** Lineal (*Outlined*), grosor constante de 2px, esquinas ligeramente redondeadas.
* **Colección base de íconos:**
* `Check Circle`: Para estado "Estoy bien".
* `Alert Triangle`: Para "Necesito ayuda".
* `User Check` / `Handshake`: Para el vínculo verificado entre panas.
* `Users` / `Proxy`: Para indicar que un tercero hizo el reporte.
* `Signal Slash`: Para indicar modo sin conexión / guardado local.



---

## 5. Componentes Clave de Interfaz (UI)

### A. Botón de Reporte Directo (Pantalla Principal)

Área táctil gigante en el centro de la pantalla. Mínimo 60px de altura para facilitar el toque bajo nerviosismo o temblor.

* **Botón 1 (Verde Salvia `#6FB98F`):** `[ Icono Check ] ESTOY BIEN`
* **Botón 2 (Terracota `#E1755F`):** `[ Icono Alert ] NECESITO AYUDA`
* **Botón 3 (Ocre Templado `#CC8B3C`):** `[ Icono Users ] REPORTAR POR UN PANA`

### B. Tarjeta de Contacto ("Mi Pana")

Diseño horizontal dentro del feed de la app:

```text
+-------------------------------------------------------+
| [ Icono Estado ]  Juan Pérez                         |
|                   +57 300 123 4567                    |
|                   Estado: ESTÁ BIEN                   |
|                   Hace 4 mins • Vía: Reporte Directo  |
+-------------------------------------------------------+

```

Si el reporte proviene de un proxy:

```text
|                   Estado: ESTÁ BIEN                   |
|                   Hace 10 mins • Vía: Proxy (+57311...) |

```

---

## 6. Tone of Voice & Copywriting (Guía de Redacción)

* **Cercano pero preciso:** Habla con la calidez del lenguaje colombiano/latino ("tu pana", "tu gente") sin perder la claridad en momentos de peligro.
* **Frases ultra-cortas:** Evita explicaciones extensas.

| Escenario | Copy Correcto (BuscoMiPana) | Copy Incorrecto (A evitar) |
| --- | --- | --- |
| **Inicio de sesión** | *"Ingresa tu celular para conectarte con tus panas."* | *"Por favor introduzca su número telefónico para iniciar la sesión."* |
| **Solicitud de Vínculo** | *"¿Quieres vincularte con [Nombre] para saber si está bien?"* | *"Envío de confirmación de handshake para relación bidireccional."* |
| **Sin Conexión** | *"Sin red. Tu estado se enviará tan pronto vuelva la señal."* | *"Error de red. No se pudo conectar al servidor remoto."* |
| **Reporte Proxy** | *"Estás reportando el estado de un pana que no tiene teléfono."* | *"Formulario de actualización delegada de información de terceros."* |
