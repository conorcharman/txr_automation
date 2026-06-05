import React, { useRef, useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, CheckCircle2, XCircle, AlertTriangle, BookOpen, Upload } from "lucide-react";
import {
  listDRRRules,
  runComplianceCheck,
  runBulkComplianceCheck,
  listDRRSubmissions,
  runCdmReport,
} from "@/api/drr";
import type {
  DRRBulkComplianceCheckResponse,
  DRRComplianceCheckRequest,
  DRRComplianceCheckResponse,
  DRRCdmReportResponse,
  DRRRuleResult,
  LeiEnrichment,
  InstrumentEnrichment,
} from "@/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  if (status === "pass")
    return (
      <Badge className="bg-green-100 text-green-800 border-green-200 gap-1">
        <CheckCircle2 size={12} /> Pass
      </Badge>
    );
  if (status === "fail")
    return (
      <Badge className="bg-red-100 text-red-800 border-red-200 gap-1">
        <XCircle size={12} /> Fail
      </Badge>
    );
  if (status === "warning")
    return (
      <Badge className="bg-amber-100 text-amber-800 border-amber-200 gap-1">
        <AlertTriangle size={12} /> Warning
      </Badge>
    );
  return <Badge variant="secondary">Not checked</Badge>;
}

function OverallBadge({ status }: { status: string }) {
  const base = "text-sm font-semibold px-3 py-1 rounded-full";
  if (status === "pass") return <span className={`${base} bg-green-100 text-green-800`}>All checks passed</span>;
  if (status === "fail") return <span className={`${base} bg-red-100 text-red-800`}>Checks failed</span>;
  return <span className={`${base} bg-amber-100 text-amber-800`}>Warnings present</span>;
}

// ---------------------------------------------------------------------------
// Rule result row with expandable provision text
// ---------------------------------------------------------------------------

function RuleResultRow({ result }: { result: DRRRuleResult }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <TableRow className="cursor-pointer hover:bg-muted/50">
        <TableCell className="font-mono text-xs text-muted-foreground w-12">
          {result.fieldNumber}
        </TableCell>
        <TableCell className="font-medium text-sm">{result.fieldName}</TableCell>
        <TableCell className="font-mono text-xs text-muted-foreground">
          {result.ruleName}
        </TableCell>
        <TableCell>{result.value ?? <span className="text-muted-foreground italic">—</span>}</TableCell>
        <TableCell>
          <StatusBadge status={result.status} />
        </TableCell>
        <TableCell className="text-sm text-red-700">{result.error ?? ""}</TableCell>
        <TableCell>
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="h-7 w-7 p-0">
              <ChevronDown
                size={14}
                className={`transition-transform ${open ? "rotate-180" : ""}`}
              />
            </Button>
          </CollapsibleTrigger>
        </TableCell>
      </TableRow>
      <CollapsibleContent asChild>
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/30 pb-3 pt-0">
            <div className="pl-4 space-y-1">
              <p className="text-xs font-medium text-muted-foreground">{result.regulation}</p>
              <p className="text-xs text-foreground leading-relaxed">{result.provision}</p>
            </div>
          </TableCell>
        </TableRow>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ---------------------------------------------------------------------------
// Bulk CSV compliance check tab (default)
// ---------------------------------------------------------------------------

const CSV_TEMPLATE_HEADERS = [
  "Report Status", "Transaction Reference Number", "Executing Entity ID", "Investment Firm Indicator",
  "Buyer ID Type", "Buyer ID", "Seller ID Type", "Seller ID", "Order Transmission Indicator",
  "Trading Date Time", "Trading Capacity", "Quantity", "Net Amount", "Venue", "Instrument ID",
  "Instrument Name", "Instrument Classification", "Notional Currency 1",
  "Price Multiplier", "Investment Decision ID", "Investment Decision Country of Branch",
  "Firm Execution ID", "Firm Execution Country of Branch", "Maturity Date", "SFT Indicator",
].join(",");

function BulkComplianceCheckTab() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [result, setResult] = useState<DRRBulkComplianceCheckResponse | null>(null);
  const [expandedRef, setExpandedRef] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: runBulkComplianceCheck,
    onSuccess: (data) => setResult(data),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedFile(e.target.files?.[0] ?? null);
    setResult(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedFile) mutation.mutate(selectedFile);
  };

  const downloadTemplate = () => {
    const blob = new Blob([CSV_TEMPLATE_HEADERS + "\n"], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "drr_compliance_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Upload size={16} /> CSV upload — bulk compliance check
          </CardTitle>
          <CardDescription>
            Upload a UnaVista CSV file containing one transaction per row. All MiFIR RTS 22 fields
            are validated in a single pass. Use the template to ensure the correct UnaVista column
            headers are present.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center gap-3">
              <Input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv"
                onChange={handleFileChange}
                className="flex-1"
              />
              <Button type="button" variant="outline" size="sm" onClick={downloadTemplate}>
                Download template
              </Button>
            </div>
            {selectedFile && (
              <p className="text-xs text-muted-foreground">
                Selected: <span className="font-medium">{selectedFile.name}</span> ({(selectedFile.size / 1024).toFixed(1)} KB)
              </p>
            )}
            <div className="flex justify-end">
              <Button type="submit" disabled={!selectedFile || mutation.isPending}>
                {mutation.isPending ? "Checking…" : "Run bulk compliance check"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {mutation.isError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4 text-red-700 text-sm">
            {String(mutation.error)}
          </CardContent>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Bulk check summary</CardTitle>
              <CardDescription>{result.totalRows} transactions checked</CardDescription>
            </CardHeader>
            <CardContent className="flex gap-6 text-sm font-medium">
              <span className="text-green-700">{result.passedRows} passed</span>
              <span className="text-red-700">{result.failedRows} failed</span>
              <span className="text-amber-700">{result.warningRows} with warnings</span>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Per-transaction results</CardTitle>
              <CardDescription>Click a row to expand per-rule details</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Transaction ref</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Pass</TableHead>
                    <TableHead className="text-right">Fail</TableHead>
                    <TableHead className="text-right">Warn</TableHead>
                    <TableHead className="w-8" />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.results.map((r) => (
                    <React.Fragment key={r.transactionRef}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() =>
                          setExpandedRef(expandedRef === r.transactionRef ? null : r.transactionRef)
                        }
                      >
                        <TableCell className="font-mono text-sm">{r.transactionRef}</TableCell>
                        <TableCell><StatusBadge status={r.overallStatus} /></TableCell>
                        <TableCell className="text-right text-green-700 font-medium">{r.passed}</TableCell>
                        <TableCell className="text-right text-red-700 font-medium">{r.failed}</TableCell>
                        <TableCell className="text-right text-amber-700 font-medium">{r.warnings}</TableCell>
                        <TableCell>
                          <ChevronDown
                            size={14}
                            className={`transition-transform ${expandedRef === r.transactionRef ? "rotate-180" : ""}`}
                          />
                        </TableCell>
                      </TableRow>
                      {expandedRef === r.transactionRef && (
                        <TableRow>
                          <TableCell colSpan={6} className="bg-muted/20 p-0">
                            <Table>
                              <TableHeader>
                                <TableRow>
                                  <TableHead className="w-12 pl-8">Field</TableHead>
                                  <TableHead>Field name</TableHead>
                                  <TableHead>DRR rule</TableHead>
                                  <TableHead>Value</TableHead>
                                  <TableHead>Status</TableHead>
                                  <TableHead>Error</TableHead>
                                </TableRow>
                              </TableHeader>
                              <TableBody>
                                {r.results.map((rule) => (
                                  <TableRow key={rule.ruleName}>
                                    <TableCell className="font-mono text-xs text-muted-foreground pl-8">
                                      {rule.fieldNumber}
                                    </TableCell>
                                    <TableCell className="font-medium text-sm">{rule.fieldName}</TableCell>
                                    <TableCell className="font-mono text-xs text-muted-foreground">{rule.ruleName}</TableCell>
                                    <TableCell className="text-sm">{rule.value ?? <span className="text-muted-foreground italic">—</span>}</TableCell>
                                    <TableCell><StatusBadge status={rule.status} /></TableCell>
                                    <TableCell className="text-sm text-red-700">{rule.error ?? ""}</TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableCell>
                        </TableRow>
                      )}
                    </React.Fragment>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single-transaction compliance check tab
// ---------------------------------------------------------------------------

const ID_TYPES = ["LEI", "CONCAT", "NIDN", "CCPT", "INTC", "BIC"];
const TRADING_CAPACITIES = ["DEAL", "MTCH", "AOTC"];
const REPORT_STATUSES = ["NEWT", "CANC"];

const EMPTY_FORM: DRRComplianceCheckRequest = {
  transactionRef: "",
  reportStatus: "NEWT",
  executingEntityId: "",
  isInvestmentFirm: "true",
  buyerId: "",
  buyerIdType: "LEI",
  sellerId: "",
  sellerIdType: "LEI",
  transmissionOfOrder: "false",
  tradingDateTime: "",
  tradingCapacity: "DEAL",
  quantity: null,
  netAmount: null,
  venue: "",
  isin: "",
  instrumentFullName: "",
  instrumentClassification: "",
  notionalCurrency1: "",
  priceMultiplier: null,
  maturityDate: "",
  investmentDecisionMaker: "",
  investmentDecisionCountry: "",
  executionWithinFirm: "",
  executionCountry: "",
  sftIndicator: "false",
};

function ComplianceCheckTab() {
  const [form, setForm] = useState<DRRComplianceCheckRequest>(EMPTY_FORM);
  const [result, setResult] = useState<DRRComplianceCheckResponse | null>(null);

  const mutation = useMutation({
    mutationFn: runComplianceCheck,
    onSuccess: (data) => setResult(data),
  });

  const set = (key: keyof DRRComplianceCheckRequest, value: string | number | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transaction fields — all RTS 22 fields</CardTitle>
          <CardDescription>
            Validate a single transaction against all MiFIR Article 26 / RTS 22 DRR rules.
            For large volumes, use the CSV Upload tab.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">

            {/* ── Report & entity ── */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Report &amp; entity identification
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2 space-y-1">
                  <Label>Transaction reference (Field 2) *</Label>
                  <Input
                    required
                    value={form.transactionRef}
                    onChange={(e) => set("transactionRef", e.target.value)}
                    placeholder="e.g. TXN-2024-00001 (max 52 chars)"
                    maxLength={52}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Report status (Field 1)</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.reportStatus ?? "NEWT"}
                    onChange={(e) => set("reportStatus", e.target.value)}
                  >
                    {REPORT_STATUSES.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>Executing entity LEI (Field 4)</Label>
                  <Input
                    value={form.executingEntityId ?? ""}
                    onChange={(e) => set("executingEntityId", e.target.value)}
                    placeholder="20-character LEI"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Investment firm indicator (Field 5)</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.isInvestmentFirm ?? "true"}
                    onChange={(e) => set("isInvestmentFirm", e.target.value)}
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>Transmission of order (Field 25)</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.transmissionOfOrder ?? "false"}
                    onChange={(e) => set("transmissionOfOrder", e.target.value)}
                  >
                    <option value="false">false</option>
                    <option value="true">true</option>
                  </select>
                </div>
              </div>
            </div>

            {/* ── Buyer & seller ── */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Buyer &amp; seller identification
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>Buyer ID (Field 7)</Label>
                  <Input
                    value={form.buyerId ?? ""}
                    onChange={(e) => set("buyerId", e.target.value)}
                    placeholder="LEI / CONCAT / NIDN..."
                  />
                </div>
                <div className="space-y-1">
                  <Label>Buyer ID type</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.buyerIdType ?? "LEI"}
                    onChange={(e) => set("buyerIdType", e.target.value)}
                  >
                    {ID_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>Seller ID (Field 16)</Label>
                  <Input
                    value={form.sellerId ?? ""}
                    onChange={(e) => set("sellerId", e.target.value)}
                    placeholder="LEI / CONCAT / NIDN..."
                  />
                </div>
                <div className="space-y-1">
                  <Label>Seller ID type</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.sellerIdType ?? "LEI"}
                    onChange={(e) => set("sellerIdType", e.target.value)}
                  >
                    {ID_TYPES.map((t) => <option key={t}>{t}</option>)}
                  </select>
                </div>
              </div>
            </div>

            {/* ── Transaction details ── */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Transaction details
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>Trading date time (Field 28)</Label>
                  <Input
                    value={form.tradingDateTime ?? ""}
                    onChange={(e) => set("tradingDateTime", e.target.value)}
                    placeholder="2024-01-15T09:30:00"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Trading capacity (Field 29)</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.tradingCapacity ?? "DEAL"}
                    onChange={(e) => set("tradingCapacity", e.target.value)}
                  >
                    {TRADING_CAPACITIES.map((c) => <option key={c}>{c}</option>)}
                  </select>
                </div>
                <div className="space-y-1">
                  <Label>Quantity (Field 30)</Label>
                  <Input
                    type="number"
                    value={form.quantity ?? ""}
                    onChange={(e) => set("quantity", e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="1000"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Net amount (Field 33)</Label>
                  <Input
                    type="number"
                    value={form.netAmount ?? ""}
                    onChange={(e) => set("netAmount", e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="10500.00"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Venue MIC (Field 36)</Label>
                  <Input
                    value={form.venue ?? ""}
                    onChange={(e) => set("venue", e.target.value)}
                    placeholder="XLON"
                    maxLength={4}
                  />
                </div>
                <div className="space-y-1">
                  <Label>SFT indicator (Field 65)</Label>
                  <select
                    className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                    value={form.sftIndicator ?? "false"}
                    onChange={(e) => set("sftIndicator", e.target.value)}
                  >
                    <option value="false">false</option>
                    <option value="true">true</option>
                  </select>
                </div>
              </div>
            </div>

            {/* ── Instrument ── */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Instrument
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>ISIN (Field 41)</Label>
                  <Input
                    value={form.isin ?? ""}
                    onChange={(e) => set("isin", e.target.value)}
                    placeholder="GB0001234567"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Instrument full name (Field 42)</Label>
                  <Input
                    value={form.instrumentFullName ?? ""}
                    onChange={(e) => set("instrumentFullName", e.target.value)}
                    placeholder="e.g. XYZ Equity Share"
                  />
                </div>
                <div className="space-y-1">
                  <Label>CFI code (Field 43)</Label>
                  <Input
                    value={form.instrumentClassification ?? ""}
                    onChange={(e) => set("instrumentClassification", e.target.value)}
                    placeholder="ESVUFR"
                    maxLength={6}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Notional currency 1 (Field 44)</Label>
                  <Input
                    value={form.notionalCurrency1 ?? ""}
                    onChange={(e) => set("notionalCurrency1", e.target.value)}
                    placeholder="GBP"
                    maxLength={3}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Price multiplier (Field 46)</Label>
                  <Input
                    type="number"
                    value={form.priceMultiplier ?? ""}
                    onChange={(e) => set("priceMultiplier", e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="1"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Maturity date (Field 54 — debt only)</Label>
                  <Input
                    value={form.maturityDate ?? ""}
                    onChange={(e) => set("maturityDate", e.target.value)}
                    placeholder="YYYY-MM-DD"
                  />
                </div>
              </div>
            </div>

            {/* ── Decision maker & execution ── */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3">
                Decision maker &amp; execution
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1">
                  <Label>Investment decision maker (Field 57)</Label>
                  <Input
                    value={form.investmentDecisionMaker ?? ""}
                    onChange={(e) => set("investmentDecisionMaker", e.target.value)}
                    placeholder="ALGO / person code"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Investment decision country (Field 58)</Label>
                  <Input
                    value={form.investmentDecisionCountry ?? ""}
                    onChange={(e) => set("investmentDecisionCountry", e.target.value)}
                    placeholder="GB"
                    maxLength={2}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Execution within firm (Field 59)</Label>
                  <Input
                    value={form.executionWithinFirm ?? ""}
                    onChange={(e) => set("executionWithinFirm", e.target.value)}
                    placeholder="ALGO / person code"
                  />
                </div>
                <div className="space-y-1">
                  <Label>Execution country (Field 60)</Label>
                  <Input
                    value={form.executionCountry ?? ""}
                    onChange={(e) => set("executionCountry", e.target.value)}
                    placeholder="GB"
                    maxLength={2}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Checking…" : "Run DRR compliance check"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {mutation.isError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4 text-red-700 text-sm">
            {String(mutation.error)}
          </CardContent>
        </Card>
      )}

      {result && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base">
                Results — {result.transactionRef}
              </CardTitle>
              <CardDescription>
                {result.totalRules} rules · {result.passed} passed · {result.failed} failed · {result.warnings} warnings
              </CardDescription>
            </div>
            <OverallBadge status={result.overallStatus} />
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">Field</TableHead>
                  <TableHead>Field name</TableHead>
                  <TableHead>DRR rule</TableHead>
                  <TableHead>Value</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead className="w-8" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.results.map((r) => (
                  <RuleResultRow key={r.ruleName} result={r} />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rule Catalogue tab
// ---------------------------------------------------------------------------

function RuleCatalogueTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["drr-rules"],
    queryFn: listDRRRules,
    staleTime: Infinity,
  });

  if (isLoading)
    return (
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base flex items-center gap-2">
          <BookOpen size={16} /> MiFIR RTS 22 — Annex I Table 2 rules
        </CardTitle>
        <CardDescription>
          Rule references sourced from ISDA DRR distribution 6.34.1
          (regulation-esma-mifir-rule.rosetta). All rules are currently{" "}
          <code className="text-xs bg-muted px-1 rounded">Not Modelled</code> in the DRR
          distribution; validation logic is implemented directly in txr_automation pending
          the DRR MiFIR release.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-16">Field</TableHead>
              <TableHead>Field name</TableHead>
              <TableHead>DRR rule name</TableHead>
              <TableHead>Regulation</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.map((rule) => (
              <Collapsible key={rule.ruleName} asChild>
                <>
                  <TableRow>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {rule.fieldNumber}
                    </TableCell>
                    <TableCell className="font-medium text-sm">{rule.fieldName}</TableCell>
                    <TableCell className="font-mono text-xs">{rule.ruleName}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {rule.regulation}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell colSpan={4} className="bg-muted/20 py-2 text-xs text-muted-foreground leading-relaxed pl-8">
                      {rule.provision}
                    </TableCell>
                  </TableRow>
                </>
              </Collapsible>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// CDM Report tab
// ---------------------------------------------------------------------------

function LeiCard({ label, data }: { label: string; data: LeiEnrichment | null }) {
  if (!data) return (
    <Card className="border-dashed">
      <CardContent className="pt-4 text-sm text-muted-foreground">{label}: no enrichment data</CardContent>
    </Card>
  );
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">{label}</CardTitle>
        <CardDescription className="font-mono text-xs">{data.lei}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <div className="flex items-center gap-2">
          <StatusBadge status={data.isValid ? "pass" : "fail"} />
          <span className="text-muted-foreground text-xs">{data.reason}</span>
        </div>
        {data.legalName && <p><span className="text-muted-foreground">Name:</span> {data.legalName}</p>}
        {data.entityStatus && <p><span className="text-muted-foreground">Status:</span> {data.entityStatus}</p>}
        {data.registrationStatus && <p><span className="text-muted-foreground">Registration:</span> {data.registrationStatus}</p>}
        {data.legalAddressCountry && <p><span className="text-muted-foreground">Country:</span> {data.legalAddressCountry}</p>}
      </CardContent>
    </Card>
  );
}

function InstrumentCard({ data }: { data: InstrumentEnrichment | null }) {
  if (!data) return (
    <Card className="border-dashed">
      <CardContent className="pt-4 text-sm text-muted-foreground">Instrument: no enrichment data</CardContent>
    </Card>
  );
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">Instrument</CardTitle>
        <CardDescription className="font-mono text-xs">{data.isin}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1 text-sm">
        <StatusBadge status={data.found ? "pass" : "fail"} />
        {data.fullName && <p><span className="text-muted-foreground">Name:</span> {data.fullName}</p>}
        {data.cfiCode && <p><span className="text-muted-foreground">CFI:</span> <span className="font-mono">{data.cfiCode}</span></p>}
        {data.mic && <p><span className="text-muted-foreground">MIC:</span> <span className="font-mono">{data.mic}</span></p>}
      </CardContent>
    </Card>
  );
}

function CdmReportTab() {
  const [form, setForm] = useState<DRRComplianceCheckRequest>(EMPTY_FORM);
  const [result, setResult] = useState<DRRCdmReportResponse | null>(null);

  const mutation = useMutation({
    mutationFn: runCdmReport,
    onSuccess: (data) => setResult(data),
  });

  const set = (key: keyof DRRComplianceCheckRequest, value: string | number | null) =>
    setForm((f) => ({ ...f, [key]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    mutation.mutate(form);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Transaction fields</CardTitle>
          <CardDescription>
            Generate a CDM-shaped <code className="text-xs bg-muted px-1 rounded">TransactionReportInstruction</code> with
            GLEIF and FIRDS enrichment.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-1">
                <Label>Transaction reference *</Label>
                <Input
                  required
                  value={form.transactionRef}
                  onChange={(e) => set("transactionRef", e.target.value)}
                  placeholder="e.g. TXN-2024-00001"
                />
              </div>

              <div className="space-y-1">
                <Label>Buyer ID (Field 7)</Label>
                <Input
                  value={form.buyerId ?? ""}
                  onChange={(e) => set("buyerId", e.target.value)}
                  placeholder="LEI / CONCAT / NIDN..."
                />
              </div>
              <div className="space-y-1">
                <Label>Buyer ID type</Label>
                <select
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={form.buyerIdType ?? "LEI"}
                  onChange={(e) => set("buyerIdType", e.target.value)}
                >
                  {ID_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>

              <div className="space-y-1">
                <Label>Seller ID (Field 16)</Label>
                <Input
                  value={form.sellerId ?? ""}
                  onChange={(e) => set("sellerId", e.target.value)}
                  placeholder="LEI / CONCAT / NIDN..."
                />
              </div>
              <div className="space-y-1">
                <Label>Seller ID type</Label>
                <select
                  className="w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
                  value={form.sellerIdType ?? "LEI"}
                  onChange={(e) => set("sellerIdType", e.target.value)}
                >
                  {ID_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </div>

              <div className="space-y-1">
                <Label>Trading date time (Field 28)</Label>
                <Input
                  value={form.tradingDateTime ?? ""}
                  onChange={(e) => set("tradingDateTime", e.target.value)}
                  placeholder="2024-01-15T09:30:00"
                />
              </div>
              <div className="space-y-1">
                <Label>ISIN (Field 41)</Label>
                <Input
                  value={form.isin ?? ""}
                  onChange={(e) => set("isin", e.target.value)}
                  placeholder="GB0001234567"
                />
              </div>

              <div className="space-y-1">
                <Label>Quantity (Field 30)</Label>
                <Input
                  type="number"
                  value={form.quantity ?? ""}
                  onChange={(e) => set("quantity", e.target.value ? parseFloat(e.target.value) : null)}
                  placeholder="1000"
                />
              </div>
              <div className="space-y-1">
                <Label>Net amount / price (Field 33)</Label>
                <Input
                  type="number"
                  value={form.netAmount ?? ""}
                  onChange={(e) => set("netAmount", e.target.value ? parseFloat(e.target.value) : null)}
                  placeholder="10500.00"
                />
              </div>

              <div className="space-y-1">
                <Label>Venue MIC (Field 36)</Label>
                <Input
                  value={form.venue ?? ""}
                  onChange={(e) => set("venue", e.target.value)}
                  placeholder="XLON"
                />
              </div>
              <div className="space-y-1">
                <Label>Investment decision maker (Field 57)</Label>
                <Input
                  value={form.investmentDecisionMaker ?? ""}
                  onChange={(e) => set("investmentDecisionMaker", e.target.value)}
                  placeholder="ALGO / person code"
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? "Generating…" : "Generate CDM report"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {mutation.isError && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-4 text-red-700 text-sm">
            {String(mutation.error)}
          </CardContent>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          {/* Compliance summary */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">Compliance summary — {result.transactionRef}</CardTitle>
              <OverallBadge status={result.complianceStatus} />
            </CardHeader>
            <CardContent className="flex gap-6 text-sm">
              <span className="text-green-700 font-medium">{result.passed} passed</span>
              <span className="text-red-700 font-medium">{result.failed} failed</span>
              <span className="text-amber-700 font-medium">{result.warnings} warnings</span>
            </CardContent>
          </Card>

          {/* Enrichment panel */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Entity &amp; instrument enrichment</CardTitle>
              <CardDescription>GLEIF Golden Copy and FIRDS cache lookups (best-effort)</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-3 gap-4">
              <LeiCard label="Buyer" data={result.enrichment.buyer} />
              <LeiCard label="Seller" data={result.enrichment.seller} />
              <InstrumentCard data={result.enrichment.instrument} />
            </CardContent>
          </Card>

          {/* CDM JSON viewer */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">CDM JSON — TransactionReportInstruction</CardTitle>
              <CardDescription>MiFIR RTS 22 structured output per ISDA Common Domain Model</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="text-xs bg-muted rounded-md p-4 overflow-auto max-h-[500px] leading-relaxed">
                {JSON.stringify(result.cdmJson, null, 2)}
              </pre>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

function SubmissionHistoryTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["drr-submissions"],
    queryFn: listDRRSubmissions,
    refetchInterval: 30_000,
  });

  if (isLoading)
    return (
      <div className="space-y-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full" />
        ))}
      </div>
    );

  if (!data?.length)
    return (
      <Card>
        <CardContent className="pt-8 text-center text-muted-foreground text-sm">
          No compliance checks yet. Run a check from the Compliance Check tab.
        </CardContent>
      </Card>
    );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Past compliance checks</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Transaction ref</TableHead>
              <TableHead>Checked at</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Pass</TableHead>
              <TableHead className="text-right">Fail</TableHead>
              <TableHead className="text-right">Warn</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((s) => (
              <TableRow key={s.submissionId}>
                <TableCell className="font-mono text-sm">{s.transactionRef}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(s.checkedAt).toLocaleString()}
                </TableCell>
                <TableCell>
                  <StatusBadge status={s.overallStatus} />
                </TableCell>
                <TableCell className="text-right text-green-700 font-medium">{s.passed}</TableCell>
                <TableCell className="text-right text-red-700 font-medium">{s.failed}</TableCell>
                <TableCell className="text-right text-amber-700 font-medium">{s.warnings}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const DRRCompliance: React.FC = () => (
  <div className="space-y-6">
    <div>
      <h1 className="text-2xl font-bold">DRR Compliance</h1>
      <p className="text-muted-foreground text-sm mt-1">
        MiFIR Article 26 / RTS 22 field validation with ISDA DRR regulatory references.
        Rule logic is implemented directly against Commission Delegated Regulation (EU) 2017/590
        Annex I Table 2, pending the DRR MiFIR rule release.
      </p>
    </div>

    <Tabs defaultValue="bulk">
      <TabsList>
        <TabsTrigger value="bulk">CSV upload</TabsTrigger>
        <TabsTrigger value="check">Single check</TabsTrigger>
        <TabsTrigger value="catalogue">Rule catalogue</TabsTrigger>
        <TabsTrigger value="history">History</TabsTrigger>
        <TabsTrigger value="cdm">CDM Report</TabsTrigger>
      </TabsList>
      <TabsContent value="bulk" className="mt-4">
        <BulkComplianceCheckTab />
      </TabsContent>
      <TabsContent value="check" className="mt-4">
        <ComplianceCheckTab />
      </TabsContent>
      <TabsContent value="catalogue" className="mt-4">
        <RuleCatalogueTab />
      </TabsContent>
      <TabsContent value="history" className="mt-4">
        <SubmissionHistoryTab />
      </TabsContent>
      <TabsContent value="cdm" className="mt-4">
        <CdmReportTab />
      </TabsContent>
    </Tabs>
  </div>
);

export default DRRCompliance;
