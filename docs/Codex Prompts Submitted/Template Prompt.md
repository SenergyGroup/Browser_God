Title
Style chat widget as STYLE_NAME (aesthetics only)

Context
Inside the `Chats` folder there is a base chat template that includes HTML, CSS, JavaScript, and custom fields. This template, together with Streamlabs, provides all actual chat functionality.

In the `example_chats` folder there are fully functional examples in text form. Use them only as examples of how visual customization can be done without breaking behavior.

Do not modify anything outside the `Chats` folder.
Do not change or add alerts.

Non negotiable constraints
The widget must remain fully functional with Streamlabs. Functionality is read only. All changes must be visual.

1. Do not change core logic, data flow, or Streamlabs integration.
2. Do not remove, rename, or repurpose IDs, classes, data attributes, or template variables that existing JavaScript or Streamlabs requires.
3. Prefer CSS and safe additional wrapper elements for changes.
4. Use JavaScript only when the effect is purely visual and cannot influence logic or integration.
5. If visuals ever conflict with behavior, preserve behavior and simplify visuals.

Core widget integration contract
Respect these exact elements and hooks. Breaking any of these will break chat.

1. Chat container
   - The element with `id="log"` and class `sl__chat__layout` is the core chat log container.
   - Do not rename, remove, or change its `id` or existing classes.
   - Do not add non message elements as direct children of `#log`.
   - You may wrap `#log` in new parent containers for layout, and you may style `#log` with CSS.

2. Chat item template
   - Do not remove or rename `<script type="text/template" id="chatlist_item">`.
   - The root element inside this template must remain a single `<div>` with:
     - `data-from="{from}"`
     - `data-id="{messageId}"`
   - The template variables `{from}`, `{messageId}`, `{color}`, `{message}` must remain and must still be used in the template.
   - You may add extra elements inside the root div (wrappers, icons, decorative spans), but you must not:
     - Change or remove the root div.
     - Change or remove the data attributes or template variables.

3. Placeholders and tokens
   - Do not rename or remove any curly brace placeholders, for example:
     `{background_color}`, `{font_size}`, `{text_color}`, `{message_hide_delay}` and all similar tokens.
   - You may introduce new placeholders if needed, but existing ones must remain unchanged.

4. JavaScript integration hooks
   - The Streamlabs platform dispatches at least these events:
     - `document.addEventListener('onLoad', function (obj) { ... })`
     - `document.addEventListener('onEventReceived', function (obj) { ... })`
   - Do not rename these events, listeners, or their function signatures.
   - Do not remove existing listeners or replace them with new ones.
   - You may add cosmetic behavior inside these existing handlers, but you must not:
     - Change how messages are fetched, inserted, sorted, or removed.
     - Intercept or replace the existing message handling logic.
   - If you are not certain a JavaScript change is purely cosmetic, do not make that change.

Message layout behavior

1. New messages must appear visually at the bottom of the message area and the list grows upward.
2. The view should keep the latest messages visible near the bottom by default unless the user manually scrolls up.
3. Do not change how messages are fetched, inserted, or processed in JavaScript. Achieve bottom alignment and layout effects through CSS and safe layout changes on the existing structure.

```
Style brief
Use this style brief as the source of all visual decisions.

Overall style name: Retro Windows 95 Aesthetic Short concept: Nostalgic interface inspired by classic mid 90s operating systems.

Design direction These are high level hints, not strict rules.

Visual mood Clean desktop nostalgia with minimal gradients, flat UI panels, and period accurate interaction cues.

Palette hints Cool grays, muted blues, soft teals, off white window backgrounds, and a few saturated accent colors like cherry red and sunshine yellow.

Shape and components Rigid window frames with beveled edges, pixel crisp borders, rectangular buttons with 3D pressed states, title bars with icon and text, dropdowns, and classic checkboxes.

Extra creative flair Subtle CRT softness, tiny system icons, mouse pointer trails, and optional startup chime references.
```

Quality and constraints
Always

1. Keep layout stable and production ready on desktop and mobile.
2. Maintain readable text and sufficient contrast.
3. Visually differentiate user vs system vs bot messages with colors, borders, or alignment.
4. Implement hover, focus, and active states using the chosen aesthetic where they make sense.
5. Keep animations subtle, short (about 150 to 250 ms), and purely cosmetic.
6. Respect the core widget integration contract above at all times.

HTML rules
Allowed:

* Add wrapper elements around `#log` for framing, borders, or background.
* Add wrapper elements inside the chat item root div (for example inner containers for name, message, badges).
* Add decorative spans, icons, or HUD like elements that do not change the meaning of existing data.

Not allowed:

* Removing or renaming required elements, IDs, classes, data attributes, or template variables.
* Changing the `id` or required classes of `#log`.
* Changing the root element or data attributes of the chat item template.

CSS rules
This is your primary canvas.

* Add a theme section at the top with CSS variables for background, primary, accent, text, success, error.
* Organize styles by sections such as layout, messages, meta (name and badges), hud, utilities.
* Use CSS to achieve:
  - Bottom aligned message stack.
  - Borders, frames, and backgrounds that express STYLE_NAME.
  - Animations for message entry and exit that remain cosmetic.
* Avoid unnecessary complexity and keep selectors clear and maintainable.

JavaScript rules
Visual JavaScript enhancements are allowed only when they are cosmetic and cannot affect chat logic or Streamlabs integration.

Preferred approach

* Keep existing JavaScript intact.
* Add new code only inside the existing `onLoad` and `onEventReceived` handlers, and only for:
  - Toggling CSS classes.
  - Triggering animations or transitions.
  - Reading custom fields for visual settings.

Allowed

1. Cosmetic transitions, small animation helpers, and purely visual state toggles tied to existing DOM events.
2. Adding or removing CSS classes that control visuals only.
3. Small helper functions that produce visual effects already triggered by existing events.
4. Timers or animation loops that do not alter or depend on data flow, message handling, or Streamlabs integration.

Not allowed

1. Changing how messages are fetched, inserted, sorted, filtered, or processed.
2. Changing event bindings, event order, or API interaction.
3. Changing IDs, data attributes, template variables, or any selector required by Streamlabs and existing code.
4. Adding external libraries or scripts.
5. Replacing or removing existing listeners for `onLoad` or `onEventReceived`.

Guiding rule
If a JavaScript change could influence message flow, data, events, or Streamlabs behavior, do not make that change.
If the change is purely visual and could be removed without changing functionality, it is allowed.

Custom fields
Use the existing custom fields as theme controls rather than hard coding values.

* Map color pickers to backgrounds, borders, or accent elements.
* Map sliders to font size, padding, spacing, or animation timing.
* Map dropdowns to layout or variant choices within the same style.
* Map font pickers to the main typeface for names and messages.

Do not change the structure of the custom fields object. You may adjust labels and default values to better fit STYLE_NAME.

Output requirements

1. Return complete updated HTML, CSS, and custom fields files inside the `Chats` folder, plus minimal JavaScript only if truly needed for visuals.
2. Preserve directory structure and file names.
3. The widget must remain functionally identical and fully compatible with Streamlabs. The changes must be visual only.
4. The `#log` container, chat item template, placeholders, and integration hooks must satisfy the core widget integration contract.

Self check before output
Before finalizing, review your result and confirm:

1. Functionality matches the original.
2. All IDs, classes, data attributes, template variables, and integration hooks remain intact and correctly named.
3. `#log` still receives only chat message items as direct children, and new messages appear at the visual bottom.
4. The aesthetic clearly matches STYLE_NAME and the direction provided in the style brief.
5. The result feels like a polished, production ready visual skin with real wow factor.
6. Any JavaScript you added is purely cosmetic and can be removed without affecting chat behavior.
