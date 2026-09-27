/** User-entered tags of a stored run, as small chips. */
export function Tags({ tags }: { tags: string[] }) {
  if (tags.length === 0) return null;
  return (
    <span className="run-tags">
      {tags.map((t) => (
        <span className="run-tag" key={t}>
          {t}
        </span>
      ))}
    </span>
  );
}
