import { useCallback, useEffect, useRef, useState } from "react";
import { messageFor } from "../pages/accounts/format";

export type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: T };

export interface Loader<T> {
  state: LoadState<T>;
  reload: () => void;
  update: (next: (current: T) => T) => void;
}

// Loads once on mount. reload() keeps the cached data on screen and only shows loading after an error.
export function useLoader<T>(load: () => Promise<T>): Loader<T> {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });
  const [version, setVersion] = useState(0);
  const loadRef = useRef(load);

  useEffect(() => {
    loadRef.current = load;
  });

  useEffect(() => {
    let active = true;
    loadRef.current().then(
      (data) => {
        if (active) {
          setState({ status: "ready", data });
        }
      },
      (error: unknown) => {
        if (active) {
          setState({ status: "error", message: messageFor(error) });
        }
      },
    );
    return () => {
      active = false;
    };
  }, [version]);

  const reload = useCallback(() => {
    setState((previous) => (previous.status === "error" ? { status: "loading" } : previous));
    setVersion((current) => current + 1);
  }, []);

  const update = useCallback((next: (current: T) => T) => {
    setState((previous) => (previous.status === "ready" ? { status: "ready", data: next(previous.data) } : previous));
  }, []);

  return { state, reload, update };
}
