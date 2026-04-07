export interface HealthResponse {
  status: string;
  version: string;
}

export type JobStatus = "pending" | "running" | "success" | "failed" | "cancelled";

export interface Job {
  id: string;
  scriptName: string;
  status: JobStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
}

export interface JobResponse {
  id: string;
  scriptName: string;
  status: JobStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  errorMessage: string | null;
  outputFiles: string[] | null;
}

export interface CreateJobRequest {
  scriptName: string;
  config: Record<string, unknown>;
}

export interface PaginatedJobs {
  items: JobResponse[];
  total: number;
}

export interface WsMessage {
  type: "log" | "status";
  data: string;
}

export interface DashboardStats {
  jobsToday: number;
  runningNow: number;
  successRate: number;
  totalSavedConfigs: number;
}

export interface SavedConfigResponse {
  id: string;
  name: string;
  scriptName: string;
  configData: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
}

export interface SavedConfigCreate {
  name: string;
  scriptName: string;
  configData: Record<string, unknown>;
}

export interface SavedConfigUpdate {
  name?: string;
  configData?: Record<string, unknown>;
}

// Accuracy Testing
export interface TestingPeriod {
  fiscalYear: string;
  quarter: string;
}

export interface BatchModeConfig {
  inputDirectory: string;
  outputDirectory: string;
  templateDirectory: string;
  logOutput?: string;
  trackerFiles?: string[];
}

export interface SingleModeConfig {
  incidentCode: string;
  inputFile: string;
  templateFile: string;
  outputFile: string;
  templateIdColumn?: string;
  templateTypeColumn?: string;
  logOutput?: string;
}

export interface RunValidationRequest {
  scriptName: string;
  testingPeriod: TestingPeriod;
  mode: "batch" | "single";
  batchConfig?: BatchModeConfig;
  singleConfig?: SingleModeConfig;
  logLevel?: string;
  dryRun?: boolean;
}

export interface RunAllRequest {
  testingPeriod: TestingPeriod;
  validationTypes: string[];
  inputDirectory: string;
  outputDirectory: string;
  templateDirectory: string;
  logLevel?: string;
  dryRun?: boolean;
}

// Replay
export interface ReplayPhase2Request {
  inputFile: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
}

export interface ReplayPhase3Request {
  inputFile: string;
  feedbackFile: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
}

export interface ReplayPhase3FinalRequest {
  inputFile: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
}

export interface ReplayMergeRequest {
  buyerFile: string;
  sellerFile: string;
  outputFile: string;
  logLevel?: string;
}

// FIRDS
export interface FirdsRefreshRequest {
  refreshType: "full" | "delta" | "auto";
  publicationDate?: string;
  logLevel?: string;
}

export interface FirdsCheckRequest {
  mode: "single" | "batch";
  isin?: string;
  inputFile?: string;
  outputFile?: string;
  logLevel?: string;
}

export interface FirdsBackfillRequest {
  startDate: string;
  endDate: string;
  logLevel?: string;
}

// GLEIF
export interface GleifRefreshRequest {
  refreshType: "full" | "delta" | "auto";
  deltaType?: "monthly" | "weekly" | "daily";
  logLevel?: string;
}

export interface GleifCheckRequest {
  mode: "single" | "batch";
  lei?: string;
  name?: string;
  inputFile?: string;
  outputFile?: string;
  logLevel?: string;
}

export interface GleifBackfillRequest {
  startDate: string;
  endDate: string;
  logLevel?: string;
}

// Utilities
export interface XlsxConverterRequest {
  mode: "single" | "batch";
  parentDir?: string;
  inputDir?: string;
  outputDir?: string;
  logLevel?: string;
}

export interface XmlConverterRequest {
  inputFile?: string;
  parentDir?: string;
  outputDir?: string;
  logLevel?: string;
}
