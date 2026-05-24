import type * as ReactNS from "react";
import { TodoListPage } from "./TodoListPage";

const host = window.QwenPaw.host;
const React: typeof ReactNS = host.React;

class TodoPlugin {
  readonly id = "todo";

  setup(): void {
    window.QwenPaw.registerRoutes?.(this.id, [
      {
        path: "/plugin/todo/list",
        component: TodoListPage as unknown as React.ComponentType,
        label: "Tasks",
        icon: "📋",
        priority: 50,
      },
    ]);
  }
}

new TodoPlugin().setup();
