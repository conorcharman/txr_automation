import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import JobCard from "@/components/JobCard";
import { fetchDashboardStats } from "@/api/dashboard";
import { listJobs } from "@/api/jobs";

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  loading: boolean;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, loading }) => (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium text-muted-foreground">
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>
      {loading ? (
        <Skeleton className="h-8 w-24" />
      ) : (
        <div className="text-2xl font-bold">{value}</div>
      )}
    </CardContent>
  </Card>
);

const Dashboard: React.FC = () => {
  const navigate = useNavigate();

  const {
    data: statsData,
    isLoading: statsLoading,
    isError: statsError,
  } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
    refetchInterval: 10_000,
  });

  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => listJobs(),
  });

  const recentJobs = jobs?.slice(0, 5) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground mt-1">
          Welcome to TXR Automation — your central hub for transaction reporting
          validation workflows.
        </p>
        {statsError && (
          <p className="mt-2 text-sm text-destructive">
            Unable to load dashboard statistics. Retrying...
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Jobs Today"
          loading={statsLoading}
          value={statsData?.jobsToday}
        />
        <StatCard
          title="Running Now"
          loading={statsLoading}
          value={
            <div className="flex items-center gap-2">
              {(statsData?.runningNow ?? 0) > 0 && (
                <div className="h-2.5 w-2.5 rounded-full bg-green-500 animate-pulse" />
              )}
              {statsData?.runningNow}
            </div>
          }
        />
        <StatCard
          title="Success Rate"
          loading={statsLoading}
          value={
            statsData != null
              ? `${Math.round(statsData.successRate * 100)}%`
              : undefined
          }
        />
        <StatCard
          title="Saved Configs"
          loading={statsLoading}
          value={statsData?.totalSavedConfigs}
        />
      </div>

      <div className="space-y-3">
        <h3 className="text-lg font-semibold tracking-tight">Recent Jobs</h3>

        {jobsLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
            <Skeleton className="h-20" />
          </div>
        ) : recentJobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">No recent jobs.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recentJobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                onClick={() => navigate(`/jobs/${job.id}`)}
              />
            ))}
          </div>
        )}

        <div className="pt-1">
          <Link
            to="/jobs"
            className="text-sm text-primary hover:underline underline-offset-2"
          >
            View all jobs →
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;

