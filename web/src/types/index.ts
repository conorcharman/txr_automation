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

export interface FileReadResponse {
  path: string;
  name: string;
  sizeBytes: number;
  content: string;
  truncated: boolean;
}

// ---------------------------------------------------------------------------
// Smart path resolution
// ---------------------------------------------------------------------------

export interface ResolvePathsRequest {
  fiscalYear: string;
  quarter: string;
  module?: string | null;
  overrides?: Record<string, string> | null;
}

export interface ResolvedPaths {
  root: string;
  kaizen: string;
  extracts: string;
  templates: string;
  output: string;
  logs: string;
}

export type JobStatus = "pending" | "running" | "waiting" | "success" | "failed" | "cancelled";

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
  configSnapshot: Record<string, unknown> | null;
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
  type: "log" | "status" | "waiting";
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
  logOutput?: string;
  logLevel?: string;
  dryRun?: boolean;
  stopOnError?: boolean;
  selectedScripts?: string[] | null;
}

// Accuracy Testing - Incident-level
export interface IncidentSelection {
  scriptKey: string;
  incidentCode: string;
}

export interface IncidentRunConfig {
  scriptName: string;
  incidentCode: string;
  inputFile: string;
  templateFile: string;
  outputFile: string;
  templateIdColumn?: string;
  templateTypeColumn?: string;
}

export interface RunIncidentsRequest {
  testingPeriod: TestingPeriod;
  incidents: IncidentRunConfig[];
  logLevel: string;
  dryRun: boolean;
  stopOnError: boolean;
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
  logOutput?: string;
}

export interface ReplayPhase2FinalRequest {
  replayOutputFile: string;
  unavistaFiles: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
  logOutput?: string;
}

export interface ReplayPhase3Request {
  inputFile: string;
  feedbackFile: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
  logOutput?: string;
}

export interface ReplayPhase3FinalRequest {
  inputFile: string;
  outputFile: string;
  fiscalYear: string;
  quarter: string;
  logLevel?: string;
  logOutput?: string;
}

export interface ReplayMergeRequest {
  buyerFile: string;
  sellerFile: string;
  outputFile: string;
  logLevel?: string;
  dryRun?: boolean;
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
  deltaType?: "24h" | "7d" | "31d";
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

// FCA Register
export interface FcaCheckRequest {
  mode: "single" | "name_search" | "batch";
  frn?: string;
  name?: string;
  inputFile?: string;
  outputFile?: string;
  permission?: string;
  logLevel?: string;
}

export interface FcaPermissionResponse {
  activityName: string;
  customerTypes: string[];
  investmentTypes: string[];
  limitations: string[];
}

export interface FcaLookupResponse {
  frn: string;
  organisationName: string;
  status: string;
  isAuthorised: boolean;
  businessType: string;
  companiesHouseNumber: string;
  statusEffectiveDate: string;
  permissions: FcaPermissionResponse[];
}

export interface FcaSearchResult {
  frn: string;
  organisationName: string;
  status: string;
}

export interface FcaSearchResponse {
  results: FcaSearchResult[];
  count: number;
}

export interface FcaLeiSearchResponse {
  lei: string;
  resolvedName: string;
  result: FcaSearchResult | null;
}

// ---------------------------------------------------------------------------
// Scheduler
// ---------------------------------------------------------------------------

export type ScheduleFrequency = "hourly" | "daily" | "weekly" | "monthly" | "quarterly" | "custom";

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

// ---------------------------------------------------------------------------
// Pipelines
// ---------------------------------------------------------------------------

export interface Pipeline {
  id: string;
  name: string;
  fiscalYear: string;
  quarter: string;
  selectedScripts: string[];
  frequency: ScheduleFrequency;
  cronExpression: string | null;
  configOverrides: Record<string, string> | null;
  stopOnError: boolean;
  isActive: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastStatus: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface PipelineCreate {
  name: string;
  fiscalYear: string;
  quarter: string;
  selectedScripts: string[];
  frequency: ScheduleFrequency;
  cronExpression?: string | null;
  configOverrides?: Record<string, string> | null;
  stopOnError?: boolean;
  isActive?: boolean;
}

export interface PipelineUpdate {
  name?: string;
  fiscalYear?: string;
  quarter?: string;
  selectedScripts?: string[];
  frequency?: ScheduleFrequency;
  cronExpression?: string | null;
  configOverrides?: Record<string, string> | null;
  stopOnError?: boolean;
  isActive?: boolean;
}

// ---------------------------------------------------------------------------
// Reconciliation Schedules
// ---------------------------------------------------------------------------

export interface ReconciliationSchedule {
  id: string;
  name: string;
  recPeriodDays: number;
  lookbackDays: number;
  selectedScripts: string[];
  frequency: string;
  cronExpression: string | null;
  configOverrides: Record<string, string> | null;
  stopOnError: boolean;
  isActive: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastStatus: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ReconciliationScheduleCreate {
  name: string;
  recPeriodDays?: number;
  lookbackDays?: number;
  selectedScripts: string[];
  frequency: string;
  cronExpression?: string | null;
  configOverrides?: Record<string, string> | null;
  stopOnError?: boolean;
  isActive?: boolean;
}

export interface ReconciliationScheduleUpdate {
  name?: string;
  recPeriodDays?: number;
  lookbackDays?: number;
  selectedScripts?: string[];
  frequency?: string;
  cronExpression?: string | null;
  configOverrides?: Record<string, string> | null;
  stopOnError?: boolean;
  isActive?: boolean;
}
