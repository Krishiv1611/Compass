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
import { workspaceApi } from "@/api";

export type CenterTab = "editor" | "preview" | "changes" | "checkpoints";
export type MobileDestination = "agent" | "files" | "editor" | "changes" | "activity";
export type WorkbenchFile = { path: string; name: string; type: "file" };
export type ViewportMode = "desktop" | "tablet" | "mobile";

export interface InspectedElement {
  tag: string;
  id?: string;
  classes?: string;
  text?: string;
  selector: string;
}

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
  checkpointsVersion: number;
  sessionsVersion: number;
  settingsRequest: { version: number; section?: string };
  dirtyWorkspaceIds: string[];
  activeSkill: string | null;
  inspectedElement: InspectedElement | null;
  viewportMode: ViewportMode;
  inspectActive: boolean;
  proDrawerOpen: boolean;
}

export type WorkbenchAction =
  | { type: "setWorkspace"; workspaceId: string | null; projectName?: string }
  | { type: "openFile"; file: WorkbenchFile }
  | { type: "closeFile"; path: string }
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
  | { type: "checkpointsChanged" }
  | { type: "sessionsChanged" }
  | { type: "openSettings"; section?: string }
  | { type: "setWorkspaceDirty"; workspaceId: string; dirty: boolean }
  | { type: "setActiveSkill"; skill: string | null }
  | { type: "setInspectedElement"; element: InspectedElement | null }
  | { type: "setViewportMode"; mode: ViewportMode }
  | { type: "setInspectActive"; active: boolean }
  | { type: "setProDrawer"; open: boolean };

const initialState: WorkbenchState = {
  activeWorkspaceId: null,
  projectName: "No project open",
  activeFile: null,
  openFiles: [],
  centerTab: "preview",
  mobileDestination: "agent",
  pendingPatchCount: 0,
  selectedContextFiles: [],
  rightPanelOpen: true,
  commandPaletteOpen: false,
  contextDrawerOpen: false,
  publishOpen: false,
  mode: "edit",
  refreshWorkspaceVersion: 0,
  patchesVersion: 0,
  checkpointsVersion: 0,
  sessionsVersion: 0,
  settingsRequest: { version: 0 },
  dirtyWorkspaceIds: [],
  activeSkill: null,
  inspectedElement: null,
  viewportMode: "desktop",
  inspectActive: false,
  proDrawerOpen: false,
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
    case "closeFile": {
      const closedIndex = state.openFiles.indexOf(action.path);
      const openFiles = state.openFiles.filter((path) => path !== action.path);
      let activeFile = state.activeFile;

      if (state.activeFile?.path === action.path) {
        if (openFiles.length === 0) {
          activeFile = null;
        } else {
          const nextIndex = Math.min(Math.max(0, closedIndex), openFiles.length - 1);
          const nextPath = openFiles[nextIndex];
          activeFile = {
            path: nextPath,
            name: nextPath.split("/").pop() || nextPath,
            type: "file",
          };
        }
      }

      return {
        ...state,
        openFiles,
        activeFile,
      };
    }
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
    case "checkpointsChanged":
      return { ...state, checkpointsVersion: state.checkpointsVersion + 1 };
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
    case "setInspectedElement": return { ...state, inspectedElement: action.element };
    case "setViewportMode": return { ...state, viewportMode: action.mode };
    case "setInspectActive": return { ...state, inspectActive: action.active };
    case "setProDrawer": return { ...state, proDrawerOpen: action.open };
  }
}

interface WorkbenchContextValue {
  state: WorkbenchState;
  dispatch: Dispatch<WorkbenchAction>;
  openFile: (file: WorkbenchFile) => void;
  closeFile: (path: string) => void;
  openChanges: (path?: string) => void;
  openPreview: () => void;
  openActivity: () => void;
  refreshWorkspace: () => void;
  refreshBackendContext: (workspaceId: string) => Promise<void>;
  setMode: (mode: ChatMode) => void;
  startNewTask: () => void;
  reviewPatches: () => void;
  openSettings: (section?: string) => void;
  notifyPatchesChanged: () => void;
  notifyCheckpointsChanged: () => void;
  setContextFiles: (files: string[]) => void;
  removeContextFile: (path: string) => void;
}

export const WorkbenchContext = createContext<WorkbenchContextValue | null>(null);

export function WorkbenchProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const openFile = useCallback((file: WorkbenchFile) => {
    dispatch({ type: "openFile", file });
    dispatch({ type: "setMobileDestination", destination: "editor" });
  }, []);
  const closeFile = useCallback((path: string) => {
    dispatch({ type: "closeFile", path });
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
  const refreshBackendContext = useCallback(async (workspaceId: string) => {
    await workspaceApi.refreshContext(workspaceId);
  }, []);
  const setMode = useCallback((mode: ChatMode) => dispatch({ type: "setMode", mode }), []);
  const startNewTask = useCallback(() => dispatch({ type: "sessionsChanged" }), []);
  const reviewPatches = useCallback(() => openChanges(), [openChanges]);
  const openSettings = useCallback((section?: string) => dispatch({ type: "openSettings", section }), []);
  const notifyPatchesChanged = useCallback(() => dispatch({ type: "patchesChanged" }), []);
  const notifyCheckpointsChanged = useCallback(() => dispatch({ type: "checkpointsChanged" }), []);
  const setContextFiles = useCallback((files: string[]) => dispatch({ type: "setContextFiles", files }), []);
  const removeContextFile = useCallback((path: string) => {
    dispatch({ type: "setContextFiles", files: state.selectedContextFiles.filter((item) => item !== path) });
  }, [state.selectedContextFiles]);

  const value = useMemo<WorkbenchContextValue>(() => ({
    state, dispatch, openFile, closeFile, openChanges, openPreview, openActivity, refreshWorkspace, refreshBackendContext,
    setMode, startNewTask, reviewPatches, openSettings, notifyPatchesChanged, notifyCheckpointsChanged,
    setContextFiles, removeContextFile,
  }), [
    state, openFile, closeFile, openChanges, openPreview, openActivity, refreshWorkspace, refreshBackendContext,
    setMode, startNewTask, reviewPatches, openSettings, notifyPatchesChanged, notifyCheckpointsChanged,
    setContextFiles, removeContextFile,
  ]);

  return <WorkbenchContext.Provider value={value}>{children}</WorkbenchContext.Provider>;
}

export function useWorkbench() {
  const value = useContext(WorkbenchContext);
  if (!value) throw new Error("useWorkbench must be used within WorkbenchProvider");
  return value;
}
