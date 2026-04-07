import React from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface StatCardProps {
  title: string;
}

const StatCard: React.FC<StatCardProps> = ({ title }) => (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
    </CardHeader>
    <CardContent>
      <Skeleton className="h-8 w-24" />
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground mt-1">
          Welcome to TXR Automation — your central hub for transaction reporting
          validation workflows.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Jobs Today" />
        <StatCard title="Running Now" />
        <StatCard title="Success Rate" />
        <StatCard title="Cached Data" />
      </div>
    </div>
  );
};

export default Dashboard;
