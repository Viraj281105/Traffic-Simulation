import { Clock, FolderOpen } from "lucide-react";
import { CloseButton } from "../ui/CloseButton";
import type { SavedSweep } from "../volumeSweepModel";

interface SavedSweepsDrawerProps {
  sweeps: SavedSweep[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
}

/** Past sweeps as the backend lists them; picking one reloads it. */
export function SavedSweepsDrawer({
  sweeps,
  selectedId,
  onSelect,
  onClose,
}: SavedSweepsDrawerProps) {
  return (
    <div className="volume-history-drawer">
      <div className="history-drawer-header">
        <div>
          <h3>
            <FolderOpen size={14} aria-hidden="true" className="uf-glyph" />{" "}
            Saved Sweep Experiments
          </h3>
          <p>
            Select any historical volume sweep run to reload its capacity curves
            and crossover metrics.
          </p>
        </div>
        <CloseButton label="Close saved sweeps" onClick={onClose} />
      </div>

      {sweeps.length > 0 ? (
        <div className="saved-sweeps-grid">
          {sweeps.map((s) => (
            <div
              key={s.id}
              className={`saved-sweep-card ${selectedId === s.id ? "active" : ""}`}
              onClick={() => {
                onSelect(s.id);
              }}
            >
              <div className="sweep-card-top">
                <span className="sweep-card-name">{s.name}</span>
                {selectedId === s.id && (
                  <span className="active-pill">Active</span>
                )}
              </div>
              <div className="sweep-card-date">
                <Clock size={14} aria-hidden="true" className="uf-glyph" />{" "}
                {new Date(s.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}{" "}
                · {new Date(s.created_at).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-saved-hint">
          <span>
            No past sweeps found. Click <strong>Run Sweep</strong> above to
            benchmark and save curves.
          </span>
        </div>
      )}
    </div>
  );
}
