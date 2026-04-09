import React from "react";
import { Clock } from "lucide-react";

interface ComingSoonProps {
  title: string;
}

const ComingSoon: React.FC<ComingSoonProps> = ({ title }) => {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
      <Clock size={48} className="text-muted-foreground" />
      <h2 className="text-2xl font-bold">{title}</h2>
      <p className="text-muted-foreground max-w-sm">
        This section is under construction and will be available in a future
        release.
      </p>
    </div>
  );
};

export default ComingSoon;
