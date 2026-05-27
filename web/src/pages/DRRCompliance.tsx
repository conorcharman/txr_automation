import React, { useState } from "react";
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
import { ChevronDown, CheckCircle2, XCircle, AlertTriangle, BookOpen } from "lucide-react";
import { listDRRRules, runComplianceCheck, listDRRSubmissions, runCdmReport } from "@/api/drr";
import type {
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
// Compliance Check tab
// ---------------------------------------------------------------------------

const ID_TYPES = ["LEI", "CONCAT", "NIDN", "CCPT", "INTC", "BIC"];

function ComplianceCheckTab() {
  const [form, setForm] = useState<DRRComplianceCheckRequest>({
    transactionRef: "",
    buyerId: "",
    buyerIdType: "LEI",
    sellerId: "",
    sellerIdType: "LEI",
    tradingDateTime: "",
    quantity: null,
    netAmount: null,
    venue: "",
    isin: "",
    investmentDecisionMaker: "",
  });
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
          <CardTitle className="text-base">Transaction fields</CardTitle>
          <CardDescription>
            Enter the key MiFIR Article 26 fields to validate against RTS 22 DRR rules.
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
  const [form, setForm] = useState<DRRComplianceCheckRequest>({
    transactionRef: "",
    buyerId: "",
    buyerIdType: "LEI",
    sellerId: "",
    sellerIdType: "LEI",
    tradingDateTime: "",
    quantity: null,
    netAmount: null,
    venue: "",
    isin: "",
    investmentDecisionMaker: "",
  });
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

    <Tabs defaultValue="check">
      <TabsList>
        <TabsTrigger value="check">Compliance check</TabsTrigger>
        <TabsTrigger value="catalogue">Rule catalogue</TabsTrigger>
        <TabsTrigger value="history">History</TabsTrigger>
        <TabsTrigger value="cdm">CDM Report</TabsTrigger>
      </TabsList>
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
