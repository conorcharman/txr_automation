export interface HealthResponse {
  status: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Filesystem browse
// ---------------------------------------------------------------------------

export interface FilesystemEntry {
  name: string;
  path: string;
  isDir: boolean;
}

export interface BrowseResponse {
  current: string;
  parent: string | null;
  entries: FilesystemEntry[];
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
  logOutput: string | null;
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
  italianTracker?: string;
  mainTracker?: string;
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
  stopOnError?: boolean;
}

// Accuracy Testing - Discovery
export interface DiscoveryRequest {
  inputDirectory: string;
}

export interface DiscoveryResult {
  scriptName: string;
  codes: string[];
  foundFiles: string[];
}

export interface DiscoveryResponse {
  results: DiscoveryResult[];
  totalFound: number;
}

// Jobs - Last Run
export interface LastRunInfo {
  scriptName: string;
  status: string;
  completedAt: string | null;
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
  dbPath?: string;
  logLevel?: string;
}

export interface FirdsCheckRequest {
  mode: "single" | "batch";
  isin?: string;
  date?: string;
  mic?: string;
  inputFile?: string;
  outputFile?: string;
  logLevel?: string;
}

export interface FirdsBackfillRequest {
  inputFile: string;
  outputFile: string;
  format?: "auto" | "incident" | "generic";
  dbPath?: string;
  skipRefresh?: boolean;
  logLevel?: string;
}

export interface FirdsLookupResponse {
  isReportable: boolean;
  reason: string;
  isin: string;
  tradeDate: string;
  mic: string | null;
  matchedMics: string[];
}

// GLEIF
export interface GleifRefreshRequest {
  refreshType: "full" | "delta" | "auto";
  deltaType?: "monthly" | "weekly" | "daily";
  dbPath?: string;
  skipIsinMap?: boolean;
  logLevel?: string;
}

export interface GleifCheckRequest {
  mode: "single" | "name_search" | "batch";
  lei?: string;
  name?: string;
  limit?: number;
  inputFile?: string;
  outputFile?: string;
  logLevel?: string;
}

export interface GleifBackfillRequest {
  inputFile: string;
  outputFile: string;
  format?: "auto" | "incident" | "generic";
  dbPath?: string;
  skipRefresh?: boolean;
  logLevel?: string;
}

export interface GleifLookupResponse {
  lei: string;
  isValid: boolean;
  reason: string;
  legalName: string;
  entityStatus: string;
  entityCategory: string;
  legalAddressCountry: string;
  registrationStatus: string;
  nextRenewalDate: string;
  successorLei: string;
  tradeDate: string | null;
}

export interface GleifSearchResult {
  lei: string;
  legalName: string;
  status: string;
  country: string;
}

export interface GleifSearchResponse {
  results: GleifSearchResult[];
  count: number;
}

// ---------------------------------------------------------------------------
// Scheduler
// ---------------------------------------------------------------------------

export type ScheduleFrequency = "hourly" | "daily" | "weekly" | "monthly" | "custom";

export interface Schedule {
  id: string;
  name: string;
  scriptName: string;
  frequency: ScheduleFrequency;
  cronExpression: string | null;
  configData: Record<string, unknown> | null;
  isActive: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastStatus: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ScheduleCreate {
  name: string;
  scriptName: string;
  frequency: ScheduleFrequency;
  cronExpression?: string | null;
  configData?: Record<string, unknown> | null;
  isActive?: boolean;
}

export interface ScheduleUpdate {
  name?: string;
  scriptName?: string;
  frequency?: ScheduleFrequency;
  cronExpression?: string | null;
  configData?: Record<string, unknown> | null;
  isActive?: boolean;
}

export interface ScheduleTriggerResponse {
  jobId: string;
  scheduleId: string;
  message: string;
}

// Utilities
export interface XlsxConverterRequest {
  mode: "single" | "batch";
  parentDir?: string;
  inputDir?: string;
  outputDir?: string;
  filterYear?: string;
  filterQuarter?: string;
  filterPhase?: string[];
  dryRun?: boolean;
  force?: boolean;
  logLevel?: string;
}

export interface XmlConverterRequest {
  inputFile?: string;
  parentDir?: string;
  outputDir?: string;
  logLevel?: string;
}
