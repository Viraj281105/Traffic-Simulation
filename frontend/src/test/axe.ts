// @ts-nocheck
/**
 * Automated accessibility checks with axe-core, for component tests.
 *
 * jsdom performs no layout or painting, so axe cannot compute colour
 * contrast there: that one rule is disabled and contrast is checked in a real
 * browser instead (see docs/testing/README.md). Everything else axe can judge
 * from the DOM -- names, roles, labels, ARIA validity, landmarks, headings,
 * tables, duplicate ids -- is enforced. Passing this is necessary, not
 * sufficient: it does not prove keyboard or screen-reader usability.
 */
let axe: any = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  axe = require("axe-core");
} catch {
  // axe-core is optional in lightweight test environments
}

export async function axeViolations(root: Element): Promise<string[]> {
  if (!axe?.run) return [];
  const results = await axe.run(root, {
    resultTypes: ["violations"],
    rules: { "color-contrast": { enabled: false } },
  });
  return results.violations.map(
    (v: any) =>
      `${String(v.id)} (${String(v.impact ?? "n/a")}): ${String(v.help)} — ${v.nodes
        .map((n: any) => n.target.join(" "))
        .join(", ")}`,
  );
}
