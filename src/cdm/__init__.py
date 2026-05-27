"""CDM mapper package.

Maps txr_automation transaction fields to CDM-compatible
TransactionReportInstruction JSON, enriched from the local GLEIF and FIRDS
caches.

This layer establishes the integration interface that cdm-drr-service will
consume when ISDA delivers working MiFIR DRR rules.  Until then it provides:

  - GLEIF enrichment: buyer/seller LEI validation and legal entity metadata
  - FIRDS enrichment: instrument full name, CFI code, and primary MIC
  - CDM structural mapping: RTS 22 fields assembled into the
    TransactionReportInstruction JSON shape

Modules:
    types    — TypedDicts for the CDM JSON structure
    enricher — Best-effort GLEIF/FIRDS enrichment
    mapper   — Pure-function: fields → CDM JSON
"""
