import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { listConfigs, createConfig, deleteConfig } from "@/api/configs";
import type { SavedConfigResponse, SavedConfigCreate } from "@/types";
import { cn } from "@/lib/utils";

interface ConfigLoaderProps {
  scriptName: string;
  currentConfig: Record<string, unknown>;
  onLoad: (config: Record<string, unknown>) => void;
}

const ConfigLoader: React.FC<ConfigLoaderProps> = ({
  scriptName,
  currentConfig,
  onLoad,
}) => {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string>("");
  const [saveMode, setSaveMode] = useState(false);
  const [saveName, setSaveName] = useState("");

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ["configs", scriptName],
    queryFn: () => listConfigs(scriptName),
  });

  const selectedConfig: SavedConfigResponse | undefined = configs.find(
    (c) => c.id === selectedId,
  );

  const createMutation = useMutation({
    mutationFn: (req: SavedConfigCreate) => createConfig(req),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configs", scriptName] });
      toast.success("Config saved");
      setSaveMode(false);
      setSaveName("");
    },
    onError: () => toast.error("Failed to save config"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteConfig(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["configs", scriptName] });
      toast.success("Config deleted");
      setSelectedId("");
    },
    onError: () => toast.error("Failed to delete config"),
  });

  const handleLoad = () => {
    if (!selectedConfig) return;
    onLoad(selectedConfig.configData);
    toast.success("Config loaded");
  };

  const handleSaveConfirm = () => {
    const trimmed = saveName.trim();
    if (!trimmed) return;
    createMutation.mutate({
      name: trimmed,
      scriptName,
      configData: currentConfig,
    });
  };

  const handleSaveKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleSaveConfirm();
    if (e.key === "Escape") {
      setSaveMode(false);
      setSaveName("");
    }
  };

  const handleDelete = () => {
    if (!selectedId) return;
    deleteMutation.mutate(selectedId);
  };

  const selectClass = cn(
    "h-9 rounded-md border border-input bg-background px-3 text-sm",
    "focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50",
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        value={selectedId}
        onChange={(e) => setSelectedId(e.target.value)}
        disabled={isLoading || configs.length === 0}
        className={selectClass}
      >
        <option value="">Load saved config...</option>
        {configs.map((c) => (
          <option key={c.id} value={c.id}>
            {c.name}
          </option>
        ))}
      </select>

      <Button
        variant="outline"
        size="sm"
        onClick={handleLoad}
        disabled={!selectedId}
      >
        Load
      </Button>

      {saveMode ? (
        <>
          <input
            autoFocus
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            onKeyDown={handleSaveKeyDown}
            placeholder="Config name..."
            className={selectClass}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={handleSaveConfirm}
            disabled={!saveName.trim() || createMutation.isPending}
          >
            Save
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setSaveMode(false);
              setSaveName("");
            }}
          >
            ×
          </Button>
        </>
      ) : (
        <Button
          variant="outline"
          size="sm"
          onClick={() => setSaveMode(true)}
        >
          Save current
        </Button>
      )}

      {selectedId && (
        <Button
          variant="destructive"
          size="sm"
          onClick={handleDelete}
          disabled={deleteMutation.isPending}
        >
          Delete
        </Button>
      )}
    </div>
  );
};

export default ConfigLoader;
