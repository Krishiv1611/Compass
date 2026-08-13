import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  type Dispatch,
  type ReactNode,
} from "react";
import type { ChatMode } from "@/types/chat";

export type CenterTab = "editor" | "preview" | "changes";
export type MobileDestination = "agent" | "files" | "editor" | "changes" | "activity";
export type WorkbenchFile = { path: string; name: string; type: "file" };

export interface WorkbenchState {
  activeWorkspaceId: string | null;
  projectName: string;
  activeFile: WorkbenchFile | null;
  openFiles: string[];
  centerTab: CenterTab;
  mobileDestination: MobileDestination;
  pendingPatchCount: number;
  selectedContextFiles: string[];
  rightPanelOpen: boolean;
  commandPaletteOpen: boolean;
  contextDrawerOpen: boolean;
  publishOpen: boolean;
  mode: ChatMode;
  refreshWorkspaceVersion: number;
  patchesVersion: number;
  sessionsVersion: number;
  settingsRequest: { version: number; section?: string };
  dirtyWorkspaceIds: string[];
  activeSkill: string | null;
}

export type WorkbenchAction =
  | { type: "setWorkspace"; workspaceId: string | null; projectName?: string }
  | { type: "openFile"; file: WorkbenchFile }
  | { type: "setCenterTab"; tab: CenterTab }
  | { type: "setMobileDestination"; destination: MobileDestination }
  | { type: "setPendingPatchCount"; count: number }
  | { type: "setContextFiles"; files: string[] }
  | { type: "setRightPanel"; open: boolean }
  | { type: "setCommandPalette"; open: boolean }
  | { type: "setContextDrawer"; open: boolean }
  | { type: "setPublish"; open: boolean }
  | { type: "setMode"; mode: ChatMode }
  | { type: "refreshWorkspace" }
  | { type: "patchesChanged" }
  | { type: "sessionsChanged" }
  | { type: "openSettings"; section?: string }
  | { type: "setWorkspaceDirty"; workspaceId: string; dirty: boolean }
  | { type: "setActiveSkill"; skill: string | null };

const initialState: WorkbenchState = {
  activeWorkspaceId: null,
  projectName: "No project open",
  activeFile: null,
  openFiles: [],
  centerTab: "editor",
  mobileDestination: "agent",
  pendingPatchCount: 0,
  selectedContextFiles: [],
  rightPanelOpen: true,
  commandPaletteOpen: false,
  contextDrawerOpen: false,
  publishOpen: false,
  mode: "ask",
  refreshWorkspaceVersion: 0,
  patchesVersion: 0,
  sessionsVersion: 0,
  settingsRequest: { version: 0 },
  dirtyWorkspaceIds: [],
  activeSkill: null,
};

function reducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case "setWorkspace":
      return {
        ...state,
        activeWorkspaceId: action.workspaceId,
        projectName: action.projectName ?? (action.workspaceId ? state.projectName : "No project open"),
        activeFile: action.workspaceId === state.activeWorkspaceId ? state.activeFile : null,
        openFiles: action.workspaceId === state.activeWorkspaceId ? state.openFiles : [],
      };
    case "openFile":
      return {
        ...state,
        activeFile: action.file,
        openFiles: state.openFiles.includes(action.file.path)
          ? state.openFiles
          : [...state.openFiles, action.file.path],
        centerTab: "editor",
      };
    case "setCenterTab": return { ...state, centerTab: action.tab };
    case "setMobileDestination": return { ...state, mobileDestination: action.destination };
    case "setPendingPatchCount": return { ...state, pendingPatchCount: Math.max(0, action.count) };
    case "setContextFiles": return { ...state, selectedContextFiles: [...new Set(action.files)] };
    case "setRightPanel": return { ...state, rightPanelOpen: action.open };
    case "setCommandPalette": return { ...state, commandPaletteOpen: action.open };
    case "setContextDrawer": return { ...state, contextDrawerOpen: action.open };
    case "setPublish": return { ...state, publishOpen: action.open };
    case "setMode": return { ...state, mode: action.mode };
    case "refreshWorkspace": return { ...state, refreshWorkspaceVersion: state.refreshWorkspaceVersion + 1 };
    case "patchesChanged":
      return { ...state, patchesVersion: state.patchesVersion + 1, refreshWorkspaceVersion: state.refreshWorkspaceVersion + 1 };
    case "sessionsChanged": return { ...state, sessionsVersion: state.sessionsVersion + 1 };
    case "openSettings":
      return { ...state, settingsRequest: { version: state.settingsRequest.version + 1, section: action.section } };
    case "setWorkspaceDirty":
      return {
        ...state,
        dirtyWorkspaceIds: action.dirty
          ? [...new Set([...state.dirtyWorkspaceIds, action.workspaceId])]
          : state.dirtyWorkspaceIds.filter(id => id !== action.workspaceId),
      };
    case "setActiveSkill": return { ...state, activeSkill: action.skill };
  }
}

interface WorkbenchContextValue {
  state: WorkbenchState;
  dispatch: Dispatch<WorkbenchAction>;
  openFile: (file: WorkbenchFile) => void;
  openChanges: (path?: string) => void;
  openPreview: () => void;
  openActivity: () => void;
  refreshWorkspace: () => void;
  setMode: (mode: ChatMode) => void;
  startNewTask: () => void;
  reviewPatches: () => void;
  openSettings: (section?: string) => void;
  notifyPatchesChanged: () => void;
  setContextFiles: (files: string[]) => void;
  removeContextFile: (path: string) => void;
}

const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const openFile = useCallback((file: WorkbenchFile) => {
    dispatch({ type: "openFile", file });
    dispatch({ type: "setMobileDestination", destination: "editor" });
  }, []);
  const openChanges = useCallback((_path?: string) => {
    dispatch({ type: "setCenterTab", tab: "changes" });
    dispatch({ type: "setMobileDestination", destination: "changes" });
  }, []);
  const openPreview = useCallback(() => dispatch({ type: "setCenterTab", tab: "preview" }), []);
  const openActivity = useCallback(() => {
    dispatch({ type: "setRightPanel", open: true });
    dispatch({ type: "setMobileDestination", destination: "activity" });
  }, []);
  const refreshWorkspace = useCallback(() => dispatch({ type: "refreshWorkspace" }), []);
  const setMode = useCallback((mode: ChatMode) => dispatch({ type: "setMode", mode }), []);
  const startNewTask = useCallback(() => dispatch({ type: "sessionsChanged" }), []);
  const reviewPatches = useCallback(() => openChanges(), [openChanges]);
  const openSettings = useCallback((section?: string) => dispatch({ type: "openSettings", section }), []);
  const notifyPatchesChanged = useCallback(() => dispatch({ type: "patchesChanged" }), []);
  const setContextFiles = useCallback((files: string[]) => dispatch({ type: "setContextFiles", files }), []);
  const removeContextFile = useCallback((path: string) => {
    dispatch({ type: "setContextFiles", files: state.selectedContextFiles.filter((item) => item !== path) });
  }, [state.selectedContextFiles]);

  const value = useMemo<WorkbenchContextValue>(() => ({
    state, dispatch, openFile, openChanges, openPreview, openActivity, refreshWorkspace,
    setMode, startNewTask, reviewPatches, openSettings, notifyPatchesChanged,
    setContextFiles, removeContextFile,
  }), [
    state, openFile, openChanges, openPreview, openActivity, refreshWorkspace,
    setMode, startNewTask, reviewPatches, openSettings, notifyPatchesChanged,
    setContextFiles, removeContextFile,
  ]);

  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench() {
  const value = useContext(WorkbenchContext);
  if (!value) throw new Error("useWorkbench must be used within WorkbenchProvider");
  return value;
}
