# Visual Identity and UI/UX Guide: FindMyPal (BuscoMiPana)

This document specifies the brand identity, visual system, and interface principles for the **BuscoMiPana** application. It is structured to serve as a prompt or technical context specification for AI tools (such as Claude) or for the development team.

---

## 1. Mission and Design Pillars

* **Purpose:** Facilitate locating and reporting the status of loved ones during emergencies and crises in Colombia and Latin America.
* **Visual Philosophy:** **Extreme Efficiency + Calm.** The priority is technical performance (an *offline-first* architecture, low 2G/3G data consumption, and minimal battery usage).
* **UI Principles:**
1. **Zero distractions:** Interface based exclusively on text, high contrast, and clean geometric shapes.
2. **Zero unnecessary network load:** No heavy profile pictures, no downloadable external fonts, no complex animations.
3. **Instant comprehension:** Critical actions must be understood in under 1 second under high-stress conditions.



---

## 2. Color Palette — "Tempered Night" (Warm Dark Mode)

The app uses **Strict Dark Mode by default** to conserve user battery life during power outages or emergencies. The palette moves away from neutral OLED black and saturated traffic-light colors: it uses a warm-tinted charcoal with softened status colors, so the app reads as calm and certain rather than alarming — without giving up the contrast that high-stress use demands.

| Color Role | Color Name | HEX Code | Usage / Application |
| --- | --- | --- | --- |
| **Main Background** | Tempered Night | `#17140F` | Base surface for the entire app (OLED power saving, warm tint). |
| **Surface / Cards** | Warm Card Gray | `#241F1A` | Modules, contact cards, and list items. |
| **Primary Brand** | Tempered Ochre | `#CC8B3C` | Neutral actions, links, secondary buttons, headers. |
| **"I'm Safe" Status** | Sage Green | `#6FB98F` | Main positive status button, "Safe" badges. |
| **"Need Help" Status** | Terracotta | `#E1755F` | Distress button, critical emergency alerts. |
| **"Pending" Status** | Soft Gold | `#E8C468` | Pending handshake requests, unverified statuses. |
| **Primary Text** | Warm White | `#F5EFE6` | Titles, primary statuses, and names (High contrast). |
| **Secondary Text** | Muted Taupe | `#B8A99A` | Metadata, timestamps, supporting instructions. |

Contrast note: solid buttons (`bg-safe`, `bg-danger`, `bg-brand`) use dark text (`#17140F`) rather than white — the sage/terracotta/ochre tones are lighter than the original saturated red/green/blue, so dark text is what actually clears AA contrast, not light.

---

## 3. Typography System

To ensure the smallest possible application size and instant load times on unstable networks, **no external font files (Google Fonts or similar) are loaded**. The app uses the native *System Font Stack* exclusively.

```css
/* Official Typography Stack */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;

```

### Typographic Hierarchy

* **Screen Titles / Alerts:** Bold (700) | 24px
* **Names / Primary Statuses:** SemiBold (600) | 18px
* **Body Text / Instructions:** Regular (400) | 14px - 16px
* **Metadata (Timestamps, Phone Numbers, Proxy info):** Regular (400) | 12px

---

## 4. Iconography & Illustrations

* **Format:** Vector SVG icons injected directly into the HTML/code (Inline SVG). Maximum size per icon: **1 KB**.
* **Style:** Line art (*Outlined*), uniform 2px stroke width, slightly rounded corners.
* **Core Icon Set:**
* `Check Circle`: For "I'm Safe" status.
* `Alert Triangle`: For "Need Help" status.
* `User Check` / `Handshake`: For verified connections between *panas*.
* `Users` / `Proxy`: Indicates a status reported by a third party.
* `Signal Slash`: Indicates offline mode / locally saved state.



---

## 5. Key UI Components

### A. Direct Reporting Buttons (Main Screen)

Giant touch area centered on the screen. Minimum 60px height to accommodate frantic or shaky touches under stress.

* **Button 1 (Sage Green `#6FB98F`):** `[ Check Icon ] I'M SAFE`
* **Button 2 (Terracotta `#E1755F`):** `[ Alert Icon ] NEED HELP`
* **Button 3 (Tempered Ochre `#CC8B3C`):** `[ Users Icon ] REPORT FOR A PANA`

### B. Contact Card ("My Pana")

Horizontal card design within the app feed:

```text
+-------------------------------------------------------+
| [ Status Icon ]  Juan Pérez                           |
|                  +57 300 123 4567                     |
|                  Status: SAFE                         |
|                  4 mins ago • Via: Direct Report      |
+-------------------------------------------------------+

```

If reported via a proxy:

```text
|                  Status: SAFE                         |
|                  10 mins ago • Via: Proxy (+57311...) |

```

---

## 6. Tone of Voice & Copywriting Guide

* **Warm yet precise:** Speaks with the approachable language of Latin America ("your *pana*", "your people") without sacrificing clarity during dangerous situations.
* **Ultra-short sentences:** Avoid lengthy explanations.

| Scenario | Correct Copy (BuscoMiPana) | Copy to Avoid |
| --- | --- | --- |
| **Login / Onboarding** | *"Enter your phone number to connect with your panas."* | *"Please enter your cellular mobile number to initialize session authentication."* |
| **Connection Request** | *"Connect with [Name] to know if they are safe?"* | *"Send bidirectional handshake verification request."* |
| **Offline State** | *"No connection. Your status will send as soon as signal returns."* | *"Network Error. Unable to establish socket connection with remote server."* |
| **Proxy Reporting** | *"You are reporting for a pana who doesn't have a phone."* | *"Third-party delegated information entry form."* |

---
