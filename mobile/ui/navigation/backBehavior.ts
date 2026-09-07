export type AndroidBackHandlerKind = "overlay" | "wizard" | "upload";
export type AndroidBackHandler = () => boolean;

export interface AndroidBackNavigation {
  readonly canGoBack: () => boolean;
  readonly exitApp: () => void;
  readonly goBack: () => void;
}

const handlerPriority: Readonly<Record<AndroidBackHandlerKind, number>> = {
  overlay: 3,
  upload: 1,
  wizard: 2,
};

type RegisteredHandler = {
  readonly handler: AndroidBackHandler;
  readonly id: number;
  readonly priority: number;
};

export class AndroidBackCoordinator {
  private readonly handlers = new Map<number, RegisteredHandler>();
  private nextHandlerId = 0;

  constructor(private readonly navigation: AndroidBackNavigation) {}

  register(kind: AndroidBackHandlerKind, handler: AndroidBackHandler): () => void {
    const id = ++this.nextHandlerId;
    this.handlers.set(id, { handler, id, priority: handlerPriority[kind] });
    return () => this.handlers.delete(id);
  }

  handleBack(): boolean {
    const handlers = [...this.handlers.values()].sort(
      (first, second) => second.priority - first.priority || second.id - first.id,
    );
    for (const registration of handlers) {
      if (registration.handler()) {
        return true;
      }
    }

    if (this.navigation.canGoBack()) {
      this.navigation.goBack();
      return true;
    }

    this.navigation.exitApp();
    return true;
  }
}
