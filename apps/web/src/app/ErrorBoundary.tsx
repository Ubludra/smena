import { Component, type ReactNode } from "react";

interface State {
  hasError: boolean;
}

/**
 * Last-resort boundary: a rendering bug shows a calm Russian message with a
 * reload action instead of a blank page (product rule §28 — no white
 * screens). Genuine coding errors are additionally visible in devtools.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: unknown): void {
    // No external telemetry in v1; console keeps the detail for debugging.
    console.error("unhandled render error", error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="splash" role="alert">
          <div className="login-card">
            <h1>Что-то пошло не так</h1>
            <p className="brand-subtitle">
              Перезагрузите страницу — данные сохранены на сервере.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => window.location.reload()}
            >
              Перезагрузить
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
