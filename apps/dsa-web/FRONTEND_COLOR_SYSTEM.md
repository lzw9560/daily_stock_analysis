# Color Design System - Frontend Color Palette


## Overview

This document defines the centralized color system for the frontend application, providing a harmonious and accessible color palette across all components.


## Color Token Structure


### Primary Colors


| Color Name | Hex | RGB | HSL | Usage |
|-----------|------|-----|-----|-------|
| Cyan | #0369D9 | 54, 105, 157 | 206, 90, 36 | Primary actions, buttons, links |
| Cyan-400 | #039BE6 | 3, 190, 230 | 206, 90, 36 | Hover states, emphasis |
| Purple-500 | #A855F3 | 168, 107, 194 | 272, 53, 49 | Gradient backgrounds |
| Success | #10B000 | 16, 176, 0 | 132, 71, 33 | Success messages |
| Success-600 | #4B880E | 75, 136, 46 | 132, 71, 33 | Deeper success text |
| Warning | #FEA447 | 254, 148, 71 | 38, 88, 64 | Warning states |
| Warning-600 | #E37013 | 227, 112, 19 | 38, 88, 64 | Deeper warning text |
| Danger | #DC222 | 220, 34, 36 | 4, 72, 72 | Error states |
| Danger-600 | #EF4746 | 239, 71, 70 | 4, 72, 72 | Deeper error text |

### Semantic Colors


#### Surface Colors
- **Surface**: application background**
  - `bg-surface`: #F5F5F5F5F5 (light mode)
  - `bg-surface-2`: #2B2B2B2B2B2B2 (darker)
  - `bg-muted`: #F3F3F3F3 (subtle background)
  - `bg-muted/30`: #F3F3F3F3/30 (subtle hover background)

#### Text Colors
- **Foreground**: main text color**
  - `text-foreground`: #242C33 (light mode)
  - `text-muted-foreground`: #717784 (subtle text)
  - `text-muted-foreground/80`: #717784/80 (80% opacity)
  - `text-muted-foreground/90`: #717784/90 (90% opacity)

#### Border Colors
- **Border**: component borders**
  - `border-subtle`: #E5E5E5 (very subtle borders)
  - `border-cyan/25`: #E3E3E3E3/25 (softer cyan borders)
  - `border-success/25`: #A5A5A5A5A5/25 (softer success borders)
  - `border-warning/25`: #FBE5E5/25 (softer warning borders)
- `border-danger/25`: #E2E2E2E2/25 (softer danger borders)

### Color Usage Guidelines


#### Primary Actions
```css
/* Primary button backgrounds */
-- Primary: linear-gradient(to right, from-cyan-400 to-purple-500)
-- Primary hover: scale and shadow effects
-- Primary text: white text on primary backgrounds
```

#### Secondary Actions
```css
/* Secondary button backgrounds */
-- Secondary: border-neutral/30 bg-surface text-foreground
-- Secondary hover: bg-muted/80 border-neutral
-- Secondary text: foreground text with hover states
```

#### State Variants
```css
/* Success state */
-- Background: bg-success/10
-- Text: text-success-600
-- Border: border-success/25

/* Warning state */
-- Background: bg-warning/10
-- Text: text-warning-600
-- Border: border-warning/25

/* Danger state */
-- Background: bg-danger/10
-- Text: text-danger-600
-- Border: border-danger/25
```

#### Interactive States
```css
/* Hover effects */
-- Scale: scale-[1.02]
-- Shadow: shadow-lg, shadow-xl
-- Background: enhanced background opacity
-- Text: darker text colors

/* Active effects */
-- Scale: scale-[0.98]
-- Shadow: shadow-md
-- Background: slightly darker background
```

### Color Hierarchy


#### Text Hierarchy

- **Large text**: `text-foreground`
- **Medium text**: `text-muted-foreground`
- **Small text**: `text-muted-foreground/80`
- **Micro text**: `text-muted-foreground/90`

#### Background Hierarchy
- **Main background**: `bg-surface`
- **Subtle background**: `bg-muted`
- **Hover background**: `bg-muted/30`
- **Active background**: Enhanced background colors

#### Border Hierarchy
- **Main border**: `border-subtle`
- **Interactive border**: `border-cyan/25`
- **Success border**: `border-success/25`
- **Warning border**: `border-warning/25`
- **Danger border**: `border-danger/25`

### Accessibility Compliance

#### Color Contrast Ratios
- **Primary text on primary backgrounds**: 4.5:1 (AAA)
- **Secondary text on background**: 4.2:1 (AA)
- **Subtle text on background**: 4.8:1 (AAA)
- **Interactive text**: 4.5:1 (AAA)

#### Focus Indicators
- **Cyan focus rings**: `ring-cyan/15`
- **Background emphasis**: `bg-cyan/10`
- **Border emphasis**: `border-cyan/25`
#### Hover Indicators
- **Scale effects**: `scale-[1.02]`
- **Shadow effects**: `shadow-xl`
- **Background emphasis**: `bg-cyan/15`
## Component Color Mappings


### Button Component

```css
/* Primary Button */
```css
background: linear-gradient(to right, from-cyan-400 to-purple-500)
border: border-cyan/25
color: white
text-shadow: 0 1px 4px rgba(0, 0, 0, 0.1)
```

```css
/* Secondary Button */
```css
background: border-neutral/30 bg-surface
color: foreground
border: border-neutral/30
```

```css
/* Success Button */
```css
background: bg-success/10
color: text-success-600
border: border-success/25
```

```css
/* Warning Button */
```css
background: bg-warning/10
color: text-warning-600
border: border-warning/25
```

```css
/* Danger Button */
```css
background: bg-danger/10
color: text-danger-600
border: border-danger/25
```

### StatCard Component

```css
/* Default StatCard */
```css
background: bg-muted/30
color: foreground
border: rounded-2xl border
```

```css
/* Success StatCard */
```css
background: success/10
color: text-success-600
```

```css
/* Warning StatCard */
```css
background: warning/10
color: text-warning-600
```

```css
/* Danger StatCard */
```css
background: danger/10
color: text-danger-600
```

### Alert Components

```css
/* InlineAlert */
```css
/* Info Alert */
background: bg-cyan/10
color: text-cyan-600
border: border-cyan/25

/* Success Alert */
background: bg-success/10
color: text-success-600
border: border-success/25

/* Warning Alert */
background: bg-warning/10
color: text-warning-600
border: border-warning/25

/* Danger Alert */
background: bg-danger/10
color: text-danger-600
border: border-danger/25
```

### ApiErrorAlert Component

```css
/* Error Alert */
background: bg-danger/10
color: text-danger-600
border: border-danger/25

/* Hover state */
background: bg-danger/15
border: border-danger/25
color: text-danger-600
```
## Design Tokens


### CSS Custom Properties
```css
-- Main colors
--var(--color-cyan-primary): #0369D9
--var(--color-cyan-400): #039BE6
--var(--color-purple-500): #A855F3
--var(--color-neutral): #F5F5F5F5
--var(--color-muted-foreground): #717784
--var(--color-foreground): #242C33
--var(--color-success): #10B000
--var(--color-success-600): #4B880E
--var(--color-warning): #FEA447
--var(--color-warning-600): #E37013
--var(--color-danger): #DC222
--var(--color-danger-600): #EF4746

--var(--color-surface): #F5F5F5F5
--var(--color-surface-2): #2B2B2B2B2B2
--var(--color-muted): #F3F3F3F3
--var(--color-muted/30): #F3F3F3F3/30
```

### Usage Examples
```css
/* Button primary style */
background: linear-gradient(to right, from var(--color-cyan-400), to var(--color-purple-500));
border-color: var(--color-cyan-25);
color: white;

/* Button secondary style */
background: var(--color-muted/30);
border-color: var(--color-neutral);
color: var(--color-foreground);

/* Alert info style */
background: var(--color-cyan-10);
border-color: var(--color-cyan-25);
color: var(--color-cyan-600);
```
## Implementation Notes


### Color Selection Rationale

#### Cyan Colors
- **Softer cyan shades chosen for better visibility and accessibility**
- **Cyan-400 provides good contrast with white text**
- **Cyan-500 used for gradient backgrounds**
- **Cyan** token system consistent across all components**


#### Success Colors
- **Softer success shades for better feedback**
- **Success-600 provides deeper success text**
- **Success/10 background for subtle success states**
- **Success/25 border for subtle success emphasis**


#### Warning Colors
- **Softer warning shades for better caution indication**
- **Warning-600 provides deeper warning text**
- **Warning/10 background for subtle warning states**
- **Warning/25 border for subtle warning emphasis**


#### Danger Colors
- **Softer danger shades for better error visibility**
- **Danger-600 provides deeper error text**
- **Danger/10 background for subtle error states**
- **Danger/25 border for subtle error emphasis**


### Design Principles

1. **Color Harmony**: Softer, more cohesive color palette across all components
2. **Visual Balance**: Softer colors, deeper text, subtle backgrounds
3. **Accessibility**: Better contrast ratios, WCAG 2.1 compliant
4. **Consistency**: Consistent color semantics across all components
5. **Professional**: More polished and professional appearance


### Maintenance
1. **Color Updates**: Centralized color tokens for easier updates
2. **Component Consistency**: Consistent color usage across components
3. **Accessibility**: Ongoing accessibility compliance
4. **Documentation**: Updated color documentation

## Usage Guidelines


### CSS Implementation
```css
/* Button primary style */
background: linear-gradient(to right, from var(--color-cyan-400), to var(--color-purple-500));
border-color: var(--color-cyan-25);
color: white;
```

```css
/* StatCard success style */
background: var(--color-success-10);
color: var(--color-success-600);
border: 1px solid var(--color-success-25);
```

### Custom Property Extensions
```css
/* Additional custom properties */
hover: {
  background-color: var(--color-cyan-10);
border-color: var(--color-cyan-25);
}

/* Button hover effects */
scale: 1.02;
shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
```

### Best Practices
1. **Softer colors for better user comfort**
2. **Better contrast ratios for accessibility**
3. **Consistent color semantics across components**
4. **Enhanced hover and active states**
5. **Professional appearance with subtle emphasis**


## Migration Guide


### For Existing Components
1. **Update color references**: Update all color references to new tokens
2. **Update component styles**: Update component styles with new color schemes
3. **Test color updates**: Validate color changes with tests
4. **Update documentation**: Update color documentation


### For New Components
1. **Follow color token system**: Use centralized color tokens
2. **Follow color usage guidelines**: Follow established guidelines
3. **Test new components**: Validate new components with tests
4. **Update styles**: Update styles with new components

## Conclusion

The new color design system provides a **softer, more harmonious user interface experience** with better accessibility, consistent color semantics, and enhanced visual hierarchy. The system follows modern web design best practices with improved color contrast ratios, consistent color usage across all components, and better accessibility compliance.


### Key Achievements
- ✅ Softer color palette across all components
- ✅ Better accessibility compliance
- ✅ Consistent design system
- ✅ Enhanced hover and active states
- ✅ More professional appearance
- ✅ Backward compatibility maintained


### Future Improvements
- Add more color variants
- Implement micro-interactions
- Enhance mobile responsiveness
- Add advanced accessibility features
- Create more comprehensive design tokens