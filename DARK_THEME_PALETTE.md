# Dark Charcoal Theme - Color Palette

## Base Colors

### Background Layers (Darkest to Lightest)
```
--bg-base:           #0a0e12  ████████  Base background (darkest)
--bg-primary:        #0f1419  ████████  Primary background
--surface-1:         #13181d  ████████  Surface layer 1
--surface-2:         #181d23  ████████  Surface layer 2
--surface-3:         #1d2329  ████████  Surface layer 3
--surface-4:         #242a31  ████████  Surface layer 4
--surface-overlay:   rgba(10, 14, 18, 0.92)  Overlay with transparency
```

### Borders (Subtle to Strong)
```
--border-subtle:     #1a1e23  ────────  Very subtle borders
--border:            #242931  ────────  Standard borders
--border-strong:     #2d333b  ────────  Emphasized borders
```

### Text Colors
```
--text-primary:      #eef4f7  ████████  Primary text (brightest)
--text-secondary:    #b9c7cf  ████████  Secondary text
--text-muted:        #8a9aa4  ████████  Muted text
--text-disabled:     #61717b  ████████  Disabled text
--text-inverse:      #081116  ████████  Inverse text (for light backgrounds)
```

## Theme Presets

All presets share the same dark charcoal base (#0a0e12 → #0f1419) with different accent colors:

### 1. Ocean (Default)
- **Accent**: #2ab7c7 (Teal/Cyan)
- **Glow**: Subtle teal and green radial gradients

### 2. Ember
- **Accent**: #f97316 (Amber/Coral)
- **Glow**: Warm orange and yellow tones

### 3. Aurora
- **Accent**: #22c55e (Green/Mint)
- **Glow**: Fresh green and teal tones

### 4. Cobalt
- **Accent**: #3b82f6 (Blue/Ice)
- **Glow**: Cool blue and cyan tones

### 5. Ruby
- **Accent**: #e11d48 (Rose/Magenta)
- **Glow**: Warm pink and magenta tones

### 6. Amethyst
- **Accent**: #8b5cf6 (Purple/Lavender)
- **Glow**: Rich purple tones

### 7. Sunset
- **Accent**: #ea580c (Orange/Peach)
- **Glow**: Warm orange and peach tones

### 8. Forest
- **Accent**: #166534 (Deep Green/Moss)
- **Glow**: Natural green tones

### 9. Sakura
- **Accent**: #db2777 (Pink/Cherry Blossom)
- **Glow**: Soft pink tones

### 10. Midnight
- **Accent**: #475569 (Dark Blue/Slate)
- **Glow**: Cool slate tones

## Semantic Colors

### Success (Green)
```
--green:             #22c55e
--green-light:       #6ee7a0
--green-dim:         #16a34a
--green-bg:          rgba(34, 197, 94, 0.1)
--green-ring:        rgba(34, 197, 94, 0.26)
```

### Warning (Amber)
```
--amber:             #f59e0b
--amber-light:       #fbc662
--amber-dim:         #d97706
--amber-bg:          rgba(245, 158, 11, 0.1)
--amber-ring:        rgba(245, 158, 11, 0.28)
```

### Error (Red)
```
--red:               #ef4444
--red-light:         #f78b8b
--red-dim:           #dc2626
--red-bg:            rgba(239, 68, 68, 0.1)
--red-ring:          rgba(239, 68, 68, 0.28)
```

## Usage Examples

### Cards
- Background: `var(--surface-1)` with subtle gradient
- Border: `var(--border-subtle)`
- Header: `var(--surface-2)` with bottom border

### Buttons
- Primary: Gradient from `var(--accent)` to `var(--accent-dim)`
- Secondary: `rgba(255, 255, 255, 0.025)` with `var(--border-subtle)`
- Ghost: Transparent with hover state

### Inputs
- Background: `rgba(255, 255, 255, 0.03)`
- Border: `var(--border-subtle)`
- Focus: `var(--accent)` border with glow

### Modals & Overlays
- Background: `var(--surface-1)` with gradient
- Backdrop: `rgba(4, 10, 14, 0.72)` with blur
- Border: `var(--border-subtle)`

## Design Principles

1. **Depth Through Layers**: Use surface layers (1-4) to create visual hierarchy
2. **Subtle Borders**: Keep borders minimal and low-contrast
3. **Accent Pops**: Let accent colors stand out against the dark base
4. **Consistent Spacing**: Use CSS variables for spacing (--space-1 through --space-16)
5. **Smooth Transitions**: All interactive elements have smooth transitions
6. **Accessibility**: Maintain sufficient contrast ratios for text readability

## Browser Compatibility

- Modern browsers (Chrome, Firefox, Safari, Edge)
- CSS custom properties (CSS variables)
- Backdrop filters for blur effects
- Radial gradients for subtle glows
