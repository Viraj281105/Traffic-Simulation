## Summary
A brief description of what this PR does, what issues it addresses (e.g. `Closes #12`), and the core changes introduced.

## Changes
- [ ] Mapped core updates in `backend/` or `frontend/`
- [ ] Updated schema definitions in `shared/schemas/` (if applicable)
- [ ] Updated architectural specifications or decision logs in `docs/` (if applicable)

## Checklist
*Please verify compliance with the following guidelines before converting this PR to ready-for-review:*
- [ ] **Directory Boundaries**: Code in `backend/` does not import from `frontend/`, and code in `frontend/` does not import from `backend/`.
- [ ] **Typings**: Code compiles with zero strict typescript warnings in `frontend/` and passes strict MyPy checks in `backend/`.
- [ ] **Formatting**: Code formatting passes `ruff format .` (Python) and `npm run format:check` (TypeScript) successfully.
- [ ] **Shared Directory Reviews**: If this PR modifies anything inside the `shared/` directory, reviews have been requested and approved by **both** Developer A and Developer B.
- [ ] **Testing**: Unit and integration tests have been run and passed successfully.
- [ ] **No Secrets**: No environment variables, passwords, or credentials have been committed.

## Testing Performed
Describe the local testing performed to verify changes:
1. Shell commands run: e.g., `pytest` or `vitest run`
2. Browser validation details: e.g. checked in Chrome 126
3. Verification results and screenshots (if UI components were modified)
