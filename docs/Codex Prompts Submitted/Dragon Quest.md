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
4. Use JavaScript only when the effect is purely visual and does not influence the logic or integration.

If visuals ever conflict with behavior, preserve behavior and simplify visuals.

Message layout behavior

1. New messages must appear visually at the bottom of the message area and the list grows upward.
2. The view should keep the latest messages visible near the bottom by default unless the user manually scrolls up.
3. Do not change how messages are fetched, inserted, or processed in JavaScript. Achieve this bottom alignment through CSS and safe layout changes whenever possible.


Style brief
Overall style name: Cozy Dragon Quest Pixel Chat
Short concept: A warm, retro JRPG party-chat window inspired by Dragon Quest, with soft pixel borders, sky blues, and little adventure details.

Design direction
These are high level hints, not strict rules.

Visual mood
A friendly inn-at-night vibe where the party is planning their next quest, presented as a classic JRPG dialog window. Feels like sitting at a wooden table with a map, lantern light, and a subtle sense of adventure. Calm, readable, nostalgic.

Palette hints
Dominant soft blues and teals inspired by Dragon Quest skies and menus. Warm accent tones like gold and amber for borders and highlights. Occasional pops of slime green and ruby red for notifications or important status. Backgrounds slightly muted so text remains very easy to read.

Shape and components
Pixel-perfect framed chat window resembling JRPG dialog boxes. Slightly rounded corners but still grid aligned. Thick, stepped pixel borders with inner bevel to mimic old game UIs. Nameplates and message bubbles that look like party dialog lines in a town or inn. Chunky, rectangular pixel buttons for actions. Subtle grid or linen texture behind the chat area, like a game menu screen.

Extra creative flair
A small HUD strip at the top or bottom showing party icons, tiny HP/MP bars, and gold count, all in pixel art. Occasional idle details like a flickering candle or gently bobbing slime in a corner. Incoming messages can appear with a tiny "dialog open" sound cue metaphor in the visuals, such as a brief sparkle or low key pixel star. System messages styled as “quest log” updates with a little scroll or book icon.

Quality and constraints
Always

1. Keep layout stable and production ready on desktop and mobile.
2. Maintain readable text and sufficient contrast.
3. Visually differentiate user vs system vs bot messages with colors, borders, or alignment.
4. Implement hover, focus, and active states using the chosen aesthetic.
5. Keep animations subtle, short (about 150 to 250 ms), and purely cosmetic.

HTML rules
Allowed:

* Add wrapper elements and extra classes for styling
* Add decorative spans or icons

Not allowed:

* Removing or renaming required elements, IDs, classes, data attributes, or template variables

CSS rules
This is your primary canvas.

* Add a theme section at the top with CSS variables for background, primary, accent, text, success, error
* Organize styles by layout, messages, inputs, buttons, HUD, utilities
* Avoid unnecessary complexity and keep selectors clear

JavaScript rules
Visual JavaScript enhancements are allowed only when they are cosmetic and cannot affect chat logic or Streamlabs integration.

Allowed

1. Cosmetic transitions, small animation helpers, and purely visual state toggles tied to existing DOM events
2. Adding or removing CSS classes that control visuals only
3. Small helper functions that produce visual effects already triggered by existing events
4. Timers or animation loops that do not alter or depend on data flow, message handling, or Streamlabs integration

Not allowed

1. Changing how messages are fetched, inserted, sorted, or processed
2. Changing event bindings, event order, or API interaction
3. Changing IDs, data attributes, template variables, or any selector required by Streamlabs and existing code
4. Adding external libraries or scripts

Guiding rule
If the JavaScript could influence message flow, data, events, or Streamlabs, do not touch it. If it is purely visual and can be removed without changing functionality, it is allowed.

Output requirements

1. Return complete updated HTML, CSS, and custom fields files inside the `Chats` folder, plus minimal JavaScript if truly needed for visuals.
2. Preserve directory structure and file names.
3. The widget must remain functionally identical and fully compatible with Streamlabs. The changes must be visual only.

Self check before output
Before finalizing, review your result and confirm:

1. Functionality matches the original.
2. All IDs, classes, data attributes, and template variables remain intact.
3. Bottom alignment for new messages is correct.
4. The aesthetic clearly matches STYLE_NAME and the direction I provided.
5. The result feels like a polished, production ready visual skin with real wow factor.
