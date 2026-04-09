---
description: "Use when writing or reviewing any TypeScript or TSX file under web/. React + TypeScript frontend conventions for the txr_automation webapp."
applyTo: "web/**"
---

# Frontend Conventions (web/)

## Stack
React 19 · TypeScript strict · Vite · Tailwind CSS 4 · shadcn/ui · React Router v7 · TanStack Query v5 · React Hook Form + Zod · Zustand · Vitest + RTL

## Components
- `React.FC<Props>` on every component, props destructured in signature
- Use shadcn/ui before building custom components
- PascalCase filenames for components, camelCase for utilities

## Data Fetching
- `useQuery` / `useMutation` from TanStack Query only — no raw `fetch()` in components
- All API functions in `web/src/api/{domain}.ts`
- Loading skeleton while fetching; error toast on failure

## Forms
- `react-hook-form` + `zodResolver` on every form
- Zod schema in same file as the form
- Inline error messages per field; submit button disabled while `isSubmitting`

## Styling
- Tailwind utility classes only — no custom CSS files
- Brand primary `#D50032` in theme as `primary`
- Dark mode via `dark:` variant

## TypeScript
- No `any` — use `unknown` then narrow
- Shared types in `web/src/types/index.ts`
- Interfaces for API response shapes; types for unions

## WebSocket
- Connect on mount, disconnect on unmount
- Exponential backoff reconnect (max 5 attempts)
- Auto-scroll LogViewer unless user has scrolled up
