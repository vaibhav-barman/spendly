---
name: "spendly-ui-designer"
description: "Design and build Spendly UI pages and components in its Flask/Jinja stack. Use for requests to design, create, build, redesign or improve any Spendly screen, even if Spendly isn't named while working in its repo."
---

# Spendly UI Designer

Create production-ready pages and components for Spendly, a personal expense tracker (https://github.com/vaibhav-barman/spendly). New UI should look like it was always part of the product and be ready to run in the existing app.

## Inputs

- Required: the page or component name. If it is missing, ask for it.
- Optional: constraints, data to display, and visual references.

## 1. Read the project first

The code changes over time, so treat the current repo as the source of truth and this file as guidance. Use the local checkout when there is one. Otherwise, clone the public repo.

Before designing, read:

- `CLAUDE.md`: project rules, architecture, and which routes are implemented or stubs
- `static/css/style.css`: design tokens and existing component classes
- `templates/base.html`: shared layout and available blocks
- The nearest existing template, plus the target template when redesigning
- `app.py`: the variables the route actually passes to the template

## 2. Stay true to the stack

Spendly is built with Flask, Jinja2, and vanilla JS. Generated code has to stay within that stack, even if a user's reference or a request's wording suggests another one:

- Use Flask with Jinja2 templates. Every page extends `base.html`.
- Use plain CSS and vanilla JS. Do not add React, Tailwind, jQuery, npm packages, or new pip packages.
- Use `url_for()` for internal links.
- Put page-specific styles in a new file at `static/css/<page>.css`, loaded through `{% block head %}`. Do not use inline `<style>` tags.
- Put page-specific JS in `{% block scripts %}`, and keep it small.
- Stay in the UI layer by default. Do not implement a stub route, add routes, or change `database/db.py` unless the user asks. If the UI needs data the route doesn't provide yet, list the template variables it expects.

## 3. Follow the design rules

Aim for a minimal, clean fintech look: modern SaaS clarity with Spendly's warm paper palette and restrained green accent.

**Tokens.** Use the variables in `style.css` instead of new hex values: `--ink*` for text, `--paper*` for surfaces, `--accent*` for primary emphasis, `--accent-2*` for secondary emphasis, `--danger*` for errors, `--border*` for lines, `--radius-*` for corners, and `--font-*` for type. The `.lp-*` landing styles contain hardcoded colors, so do not copy those values. If a token is truly missing, add it to `:root` and say so.

**Type.** Use `--font-display` (DM Serif Display) for page titles, card titles, and large totals. Use `--font-body` (DM Sans) for everything else. Show amounts in rupees with Indian digit grouping (₹18,240), and use `font-variant-numeric: tabular-nums` where numbers need to line up.

**Spacing.** Use an 8px grid for new layout: 8, 16, 24, 32, 48, or 64px (0.5rem to 4rem), with 4px for small icon-to-label gaps. Reused component classes keep their existing internal spacing, because matching them matters more than forcing them onto the grid.

**Surfaces.** Use card-based layouts: `--paper-card`, a 1px `--border`, `--radius-md` (or `--radius-lg` for large panels), and a soft shadow no stronger than `0 8px 40px rgba(0,0,0,0.06)`. Use one or two levels of elevation at most.

**Hierarchy.** Each screen should make its main number or action obvious within a second or two. Group related information and leave out decoration that has no purpose. A tracker is used often, so clear, scannable data matters more than visual flair.

**Reuse.** Reuse existing classes such as `.btn-primary`, `.btn-ghost`, `.form-group`, `.form-input`, `.auth-error`, and the card patterns before writing new ones. Prefix new classes by page or component (for example `.exp-table`) so they don't collide.

**Responsive.** Build mobile-first where practical and follow the existing 900px and 600px breakpoints. There must be no horizontal page scroll at 360px wide. On small screens, reflow wide tables into stacked rows or cards.

**States.** Design the real states, not only the full one: empty, error, long values, and loading where it applies. Empty states should point to the next action, such as adding a first expense.

**Accessibility.** Use semantic HTML, labels tied to inputs, visible `:focus-visible` styles, sufficient contrast, and touch targets of about 44px. Never use color alone to show meaning, such as over or under budget.

## 4. Use Lucide icons

Lucide is the only icon library for Spendly, so a screen never mixes icon styles. Use icons where they help recognition, such as categories, actions, and status. Give icon-only buttons an `aria-label`, and mark decorative icons `aria-hidden="true"`. Keep the existing `◈` brand mark.

Use one of these two methods, and follow whichever the project already uses:

- **CDN script.** This suits pages with many icons. Use `<i data-lucide="wallet"></i>` in the markup, then load Lucide once in `{% block scripts %}` from an exact version, such as `https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js`, and call `lucide.createIcons()`. If several pages need it, move the script to `base.html` rather than repeating it. Call `lucide.createIcons()` again after JS adds new icons to the page.
- **Inline SVG.** This suits a few icons on a page, or anything that must render without waiting for JS. Copy the path data from Lucide's official source rather than drawing it from memory, because recalled paths are often subtly wrong. Put repeated icons in a Jinja macro in `templates/macros/icons.html`.

Check that each icon name exists in Lucide before using it, because an unknown name renders nothing.

## 5. Consistency rule

Match the existing design. If the code doesn't settle how something should look, such as a new pattern with no precedent or a reference that conflicts with the current style, ask the user for screenshots of the existing design before building. Don't invent a new visual direction.

For an explicit redesign, keep the design tokens and overall identity unless the user asks for a new look.

## 6. Output format

When working in a checkout, write the code to the project files. Otherwise, present each file in its own labeled code block. Use this structure:

### UI structure
Keep this brief: the layout, key sections, and important UX decisions with a short reason for each.

### Code
Organize it by file path, with clean CSS, modular components, and minimal boilerplate. Use Jinja `{% include %}` or macros for anything likely to repeat. Don't dump one undifferentiated block of code, and only include comments that explain something non-obvious.

### Integration notes
Include only what applies: template variables the route must pass, new tokens or macros, and how to view the result.

## 7. Check it before handing it over

When you can run the app (`python app.py`, port 5001), load the page and check it at desktop and 360px widths, including empty and error states. Fix what you find. If you can't run it, say so rather than implying it was tested.

## Avoid

- Generic or dated UI, including default-looking Bootstrap styles, heavy gradients, and loud colors
- Clutter, one-off styles, and random colors, radii, or shadows
- Unstructured code dumps
- Invented data presented as real. Sample data is fine in a preview, but the template must render real variables.