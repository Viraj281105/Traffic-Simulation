import { createContext, useContext } from "react";
import type { SceneTheme } from "./render";
import type { SceneData } from "./sceneData";

/** The recorded scene data, or null while its chunk is still loading. */
export const SceneContext = createContext<SceneData | null>(null);

export function useSceneData(): SceneData | null {
  return useContext(SceneContext);
}

/** The page's light or dark theme, for the canvases that follow it. */
export const ThemeContext = createContext<SceneTheme>("dark");

export function useSceneTheme(): SceneTheme {
  return useContext(ThemeContext);
}
