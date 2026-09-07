import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { useMobileAuth } from "../auth/MobileAuthProvider";
import { openUserEncryptedDatabase } from "./encryptedUserDatabase";
import { UserQueryCachePersistence } from "./queryPersistence";

export interface MobileQueryCacheBoundaryProps {
  readonly children: ReactNode;
}

export function MobileQueryCacheBoundary({ children }: MobileQueryCacheBoundaryProps) {
  const auth = useMobileAuth();
  const queryClient = useQueryClient();
  const persistence = useMemo(
    () => new UserQueryCachePersistence({ openDatabase: openUserEncryptedDatabase }),
    [],
  );
  const [readyUserId, setReadyUserId] = useState<string | null>(null);
  const userId = auth.status === "signed_in" ? auth.user?.id ?? null : null;
  const needsHydration = auth.status === "signed_in" && userId !== null;

  useEffect(() => {
    let active = true;
    setReadyUserId(null);
    void persistence.setUser(userId, queryClient).then(
      () => {
        if (active) setReadyUserId(userId);
      },
      () => {
        if (active) setReadyUserId(userId);
      },
    );
    return () => {
      active = false;
    };
  }, [persistence, queryClient, userId]);

  useEffect(() => () => {
    void persistence.dispose(queryClient);
  }, [persistence, queryClient]);

  if (needsHydration && readyUserId !== userId) return null;
  return children;
}
