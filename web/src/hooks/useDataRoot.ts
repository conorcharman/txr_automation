import { useQuery } from "@tanstack/react-query";
import { getFilesystemConfig } from "@/api/filesystem";

/**
 * Returns the server's configured data root directory.
 *
 * Queries ``GET /api/filesystem/config`` once (staleTime: Infinity) and
 * falls back to the Docker default ``/app/data`` while loading or on error.
 *
 * @returns The resolved absolute path to the data directory.
 */
export function useDataRoot(): string {
  const { data } = useQuery({
    queryKey: ["filesystem-config"],
    queryFn: getFilesystemConfig,
    staleTime: Infinity,
  });
  return data?.dataRoot ?? "/app/data";
}
