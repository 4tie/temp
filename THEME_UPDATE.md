# Dark Charcoal Theme Update

## Overview
All theme presets have been updated to use a consistent dark charcoal background across the entire application, creating a unified dark vibe throughout.

## Changes Made

### 1. Base Background Colors (base.css)
Updated the root CSS variables to use darker charcoal tones:

- **--bg-base**: `#0a0e12` (darkest background)
- **--bg-primary**: `#0f1419` (primary background)
- **--surface-1**: `#13181d` (surface layer 1)
- **--surface-2**: `#181d23` (surface layer 2)
- **--surface-3**: `#1d2329` (surface layer 3)
- **--surface-4**: `#242a31` (surface layer 4)
- **--surface-overlay**: `rgba(10, 14, 18, 0.92)` (overlay with transparency)

### 2. Border Colors
Updated borders to be more subtle and match the dark theme:

- **--border-subtle**: `#1a1e23` (very subtle borders)
- **--border**: `#242931` (standard borders)
- **--border-strong**: `#2d333b` (emphasized borders)

### 3. All Theme Presets
Updated all 10 theme presets to use the same dark charcoal background:

1. **Ocean** - Teal and cyan accents
2. **Ember** - Amber and coral accents
3. **Aurora** - Green and mint accents
4. **Cobalt** - Blue and ice accents
5. **Ruby** - Rose and magenta accents
6. **Amethyst** - Purple and lavender accents
7. **Sunset** - Orange and peach accents
8. **Forest** - Deep green and moss accents
9. **Sakura** - Pink and cherry blossom accents
10. **Midnight** - Dark blue and slate accents (updated accent colors to be lighter)

Each preset now uses:
- **--bg-gradient-start**: `#0a0e12`
- **--bg-gradient-end**: `#0f1419`
- Reduced glow intensities for a more subtle effect

### 4. Theme Manager (theme.js)
Updated all preset metadata to reflect the unified background color `#0a0e12`.

## Benefits

1. **Consistency**: All themes now share the same dark charcoal foundation
2. **Eye Comfort**: Darker backgrounds reduce eye strain
3. **Professional Look**: Unified dark theme creates a cohesive, modern appearance
4. **Accent Focus**: Dark backgrounds make accent colors pop more effectively
5. **Clean Design**: Subtle borders and surfaces create depth without distraction

## How Themes Work

- Themes are stored in `localStorage` with key `4tie_theme_preset`
- Default theme is `ocean`
- Users can switch themes via the Settings page
- Theme is applied on page load via inline script in base.html
- All themes maintain the same dark charcoal base, only accent colors change

## Files Modified

1. `/static/css/base.css` - Updated all CSS variables and theme presets
2. `/static/js/core/theme.js` - Updated preset metadata backgrounds

## Testing

To verify the changes:
1. Open the application
2. Navigate to Settings
3. Switch between different theme presets
4. Confirm all themes maintain the dark charcoal background
5. Verify accent colors change appropriately
6. Check that borders and surfaces are subtle and consistent
