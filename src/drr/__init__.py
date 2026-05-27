"""DRR — Digital Regulatory Reporting traceability layer.

Maps txr_automation validators to MiFIR RTS 22 (Commission Delegated Regulation
(EU) 2017/590) reporting rules as defined in the ISDA DRR model. Rule references
are sourced from regulation-esma-mifir-rule.rosetta (DRR distribution 6.34.1).

When DRR MiFIR rules are implemented in a future release, the compiled JARs from
the cdm-drr-service will replace the inline validation logic here while the rule
identifiers and regulatory references remain stable.
"""
